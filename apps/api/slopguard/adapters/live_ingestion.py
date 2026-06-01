"""Live Content Ingestion Engine.

Continuously pulls real content from public APIs, scores it, and feeds
the live ticker. This makes SlopGuard feel alive — judges see real
content being scored in real time from across the internet.

Sources:
  - Hacker News    → content, social_news
  - Dev.to         → content, docs
  - GitHub Issues  → code_review
  - GitHub Commits → code_review
  - Reddit         → social_news, communications
  - Stack Overflow → docs, code_review
  - arXiv          → academia
  - Wikipedia      → content, docs
  - CrossRef       → academia
  - PubMed         → academia

Run as background thread: ingestion starts automatically when the API starts.
GET /live/feed   → last 50 scored items with source, text preview, score
GET /live/stats  → ingestion stats (items/min, domain breakdown, slop rate)
"""

from __future__ import annotations

import json
import re
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict, deque
from dataclasses import dataclass, field
from typing import Literal


# ---------------------------------------------------------------------------
# Shared live feed — last 200 scored items
# ---------------------------------------------------------------------------

@dataclass
class LiveItem:
    source: str
    domain: str
    text_preview: str
    full_text: str
    score: float
    oversight: str
    signals: list[dict]
    timestamp: float = field(default_factory=time.time)
    url: str = ""
    title: str = ""


_live_feed: deque[LiveItem] = deque(maxlen=200)
_ingestion_stats: dict = {
    "total_ingested": 0,
    "total_scored": 0,
    "slop_count": 0,
    "domain_counts": defaultdict(int),
    "source_counts": defaultdict(int),
    "errors": 0,
    "started_at": None,
    "last_item_at": None,
    "items_per_minute": 0.0,
}
_ingestion_lock = threading.Lock()
_ingestion_task = None
_stop_event = threading.Event()


def get_live_feed(limit: int = 50) -> list[dict]:
    with _ingestion_lock:
        items = list(_live_feed)[-limit:]
    return [
        {
            "source": i.source,
            "domain": i.domain,
            "title": i.title,
            "text_preview": i.text_preview,
            "score": i.score,
            "oversight": i.oversight,
            "timestamp": i.timestamp,
            "url": i.url,
            "top_signal": i.signals[0]["name"] if i.signals else "unknown",
            "flagged_count": sum(1 for s in i.signals if s.get("score", 1) < 0.42),
        }
        for i in reversed(items)
    ]


def get_ingestion_stats() -> dict:
    with _ingestion_lock:
        stats = dict(_ingestion_stats)
        stats["domain_counts"] = dict(_ingestion_stats["domain_counts"])
        stats["source_counts"] = dict(_ingestion_stats["source_counts"])
        if stats["started_at"]:
            elapsed = time.time() - stats["started_at"]
            stats["items_per_minute"] = round(stats["total_scored"] / max(elapsed / 60, 0.01), 1)
            stats["uptime_seconds"] = round(elapsed)
        stats["slop_rate"] = round(
            stats["slop_count"] / max(stats["total_scored"], 1), 3
        )
    return stats


# ---------------------------------------------------------------------------
# HTTP helper
# ---------------------------------------------------------------------------

def _get(url: str, timeout: int = 8) -> dict | list | str | None:
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "SlopGuard-LiveIngestion/0.1", "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as r:
            raw = r.read()
            try:
                return json.loads(raw)
            except Exception:
                return raw.decode("utf-8", errors="replace")
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Source fetchers — each returns list of (domain, title, text, url)
# ---------------------------------------------------------------------------

def _fetch_hacker_news(limit: int = 8) -> list[tuple[str, str, str, str]]:
    """Top HN stories — content/social_news domain."""
    ids = _get("https://hacker-news.firebaseio.com/v0/topstories.json")
    if not ids or not isinstance(ids, list):
        return []
    results = []
    for story_id in ids[:limit * 2]:
        item = _get(f"https://hacker-news.firebaseio.com/v0/item/{story_id}.json")
        if not item or not isinstance(item, dict):
            continue
        title = item.get("title", "")
        text = item.get("text", "") or ""
        url = item.get("url", f"https://news.ycombinator.com/item?id={story_id}")
        if not title:
            continue
        content = f"{title}\n\n{text}".strip() if text else title
        if len(content) < 20:
            continue
        domain = "social_news" if not text else "content"
        results.append((domain, title, content[:800], url))
        if len(results) >= limit:
            break
    return results


def _fetch_devto(limit: int = 8) -> list[tuple[str, str, str, str]]:
    """Dev.to articles — content/docs domain."""
    data = _get("https://dev.to/api/articles?per_page=15&top=7")
    if not data or not isinstance(data, list):
        return []
    results = []
    for article in data[:limit * 2]:
        title = article.get("title", "")
        description = article.get("description", "") or ""
        tags = article.get("tag_list", [])
        url = article.get("url", "")
        if not title or len(description) < 20:
            continue
        content = f"{title}\n\n{description}"
        domain = "docs" if any(t in tags for t in ["tutorial", "documentation", "beginners"]) else "content"
        results.append((domain, title, content[:700], url))
        if len(results) >= limit:
            break
    return results


def _fetch_github_issues(limit: int = 6) -> list[tuple[str, str, str, str]]:
    """GitHub issues from active repos — code_review domain."""
    repos = [
        "django/django", "pallets/flask", "psf/requests",
        "pytest-dev/pytest", "microsoft/TypeScript", "facebook/react",
    ]
    import random
    repo = random.choice(repos)
    data = _get(f"https://api.github.com/repos/{repo}/issues?state=closed&per_page=20&sort=updated")
    if not data or not isinstance(data, list):
        return []
    results = []
    for issue in data:
        if issue.get("pull_request"):
            continue  # skip PRs, only issues
        title = issue.get("title", "")
        body = issue.get("body", "") or ""
        url = issue.get("html_url", "")
        if not title or len(body) < 30:
            continue
        content = f"{title}\n\n{body}"[:800]
        results.append(("code_review", title, content, url))
        if len(results) >= limit:
            break
    return results


def _fetch_github_commits(limit: int = 6) -> list[tuple[str, str, str, str]]:
    """GitHub commit messages — code_review domain."""
    repos = [
        "torvalds/linux", "python/cpython", "rust-lang/rust",
        "golang/go", "kubernetes/kubernetes", "ansible/ansible",
    ]
    import random
    repo = random.choice(repos)
    data = _get(f"https://api.github.com/repos/{repo}/commits?per_page=20")
    if not data or not isinstance(data, list):
        return []
    results = []
    for commit in data:
        msg = commit.get("commit", {}).get("message", "")
        url = commit.get("html_url", "")
        if not msg or len(msg) < 20:
            continue
        title = msg.split("\n")[0]
        results.append(("code_review", title, msg[:600], url))
        if len(results) >= limit:
            break
    return results


def _fetch_reddit(limit: int = 6) -> list[tuple[str, str, str, str]]:
    """Reddit posts — social_news and communications."""
    subs = [
        ("worldnews", "social_news"),
        ("technology", "social_news"),
        ("ExperiencedDevs", "communications"),
        ("cscareerquestions", "communications"),
        ("programming", "content"),
    ]
    import random
    sub, domain = random.choice(subs)
    data = _get(f"https://www.reddit.com/r/{sub}/hot.json?limit=20")
    if not data or not isinstance(data, dict):
        return []
    posts = data.get("data", {}).get("children", [])
    results = []
    for post in posts:
        p = post.get("data", {})
        title = p.get("title", "")
        selftext = p.get("selftext", "") or ""
        url = f"https://reddit.com{p.get('permalink', '')}"
        if not title:
            continue
        content = f"{title}\n\n{selftext}".strip() if selftext else title
        if len(content) < 20:
            continue
        results.append((domain, title, content[:700], url))
        if len(results) >= limit:
            break
    return results


def _fetch_stackoverflow(limit: int = 5) -> list[tuple[str, str, str, str]]:
    """Stack Overflow questions — docs/code_review domain."""
    data = _get(
        "https://api.stackexchange.com/2.3/questions"
        "?order=desc&sort=votes&site=stackoverflow&pagesize=15&filter=withbody"
    )
    if not data or not isinstance(data, dict):
        return []
    results = []
    for q in data.get("items", []):
        title = q.get("title", "")
        body = q.get("body", "") or ""
        # Strip HTML tags
        body = re.sub(r"<[^>]+>", " ", body)
        body = re.sub(r"\s+", " ", body).strip()
        url = q.get("link", "")
        if not title or len(body) < 30:
            continue
        content = f"{title}\n\n{body}"[:700]
        results.append(("docs", title, content, url))
        if len(results) >= limit:
            break
    return results


def _fetch_arxiv(limit: int = 4) -> list[tuple[str, str, str, str]]:
    """arXiv abstracts — academia domain."""
    queries = ["cat:cs.AI", "cat:cs.LG", "cat:cs.CL", "cat:stat.ML"]
    import random
    query = random.choice(queries)
    encoded = urllib.parse.quote(query)
    try:
        req = urllib.request.Request(
            f"https://export.arxiv.org/api/query?search_query={encoded}&max_results={limit * 2}&sortBy=submittedDate",
            headers={"User-Agent": "SlopGuard/0.1"},
        )
        with urllib.request.urlopen(req, timeout=12) as r:
            xml = r.read().decode("utf-8", errors="replace")
    except Exception:
        return []

    titles = re.findall(r"<title[^>]*>(.*?)</title>", xml, re.DOTALL)[1:]  # skip feed title
    abstracts = re.findall(r"<summary[^>]*>(.*?)</summary>", xml, re.DOTALL)
    links = re.findall(r'<id>(https://arxiv\.org/abs/[^<]+)</id>', xml)

    results = []
    for i, abstract in enumerate(abstracts[:limit]):
        abstract = re.sub(r"\s+", " ", abstract).strip()
        title = re.sub(r"\s+", " ", titles[i]).strip() if i < len(titles) else "arXiv paper"
        url = links[i] if i < len(links) else "https://arxiv.org"
        if len(abstract) < 50:
            continue
        content = f"{title}\n\n{abstract}"
        results.append(("academia", title, content[:800], url))
    return results


def _fetch_wikipedia(limit: int = 4) -> list[tuple[str, str, str, str]]:
    """Wikipedia article summaries — content/docs domain."""
    topics = [
        "Machine_learning", "Artificial_intelligence", "Python_(programming_language)",
        "Docker_(software)", "Kubernetes", "PostgreSQL", "Redis", "GraphQL",
        "REST_API", "Microservices", "DevOps", "Continuous_integration",
        "Test-driven_development", "Agile_software_development",
    ]
    import random
    results = []
    for topic in random.sample(topics, min(limit * 2, len(topics))):
        data = _get(f"https://en.wikipedia.org/api/rest_v1/page/summary/{topic}")
        if not data or not isinstance(data, dict):
            continue
        title = data.get("title", "")
        extract = data.get("extract", "") or ""
        url = data.get("content_urls", {}).get("desktop", {}).get("page", "")
        if not extract or len(extract) < 50:
            continue
        results.append(("content", title, extract[:700], url))
        if len(results) >= limit:
            break
    return results


def _fetch_crossref(limit: int = 4) -> list[tuple[str, str, str, str]]:
    """CrossRef paper abstracts — academia domain."""
    queries = ["machine learning evaluation", "AI detection benchmark", "natural language processing"]
    import random
    query = urllib.parse.quote(random.choice(queries))
    # Filter for journal articles which are more likely to have abstracts
    data = _get(
        f"https://api.crossref.org/works?query={query}&rows={limit * 4}"
        f"&filter=type:journal-article&select=title,abstract,DOI,URL,type"
    )
    if not data or not isinstance(data, dict):
        return []
    results = []
    for item in data.get("message", {}).get("items", []):
        title_list = item.get("title", [])
        title = title_list[0] if title_list else ""
        abstract = item.get("abstract", "") or ""
        if not abstract:
            continue
        abstract = re.sub(r"<[^>]+>", " ", abstract)
        abstract = re.sub(r"\s+", " ", abstract).strip()
        doi = item.get("DOI", "")
        url = f"https://doi.org/{doi}" if doi else ""
        if not title or len(abstract) < 50:
            continue
        content = f"{title}\n\n{abstract}"
        results.append(("academia", title, content[:800], url))
        if len(results) >= limit:
            break
    return results


def _fetch_pubmed(limit: int = 4) -> list[tuple[str, str, str, str]]:
    """PubMed abstracts — academia domain."""
    terms = ["artificial intelligence clinical", "machine learning diagnosis", "NLP biomedical"]
    import random
    term = urllib.parse.quote(random.choice(terms))
    search = _get(
        f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
        f"?db=pubmed&term={term}&retmax={limit}&retmode=json"
    )
    if not search or not isinstance(search, dict):
        return []
    ids = search.get("esearchresult", {}).get("idlist", [])
    if not ids:
        return []
    id_str = ",".join(ids[:limit])
    fetch = _get(
        f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/efetch.fcgi"
        f"?db=pubmed&id={id_str}&retmode=xml&rettype=abstract"
    )
    if not fetch or not isinstance(fetch, str):
        return []
    titles = re.findall(r"<ArticleTitle>(.*?)</ArticleTitle>", fetch, re.DOTALL)
    abstracts = re.findall(r"<AbstractText[^>]*>(.*?)</AbstractText>", fetch, re.DOTALL)
    results = []
    for i, abstract in enumerate(abstracts[:limit]):
        abstract = re.sub(r"\s+", " ", abstract).strip()
        title = titles[i] if i < len(titles) else "PubMed article"
        if len(abstract) < 50:
            continue
        content = f"{title}\n\n{abstract}"
        url = f"https://pubmed.ncbi.nlm.nih.gov/{ids[i]}/" if i < len(ids) else ""
        results.append(("academia", title, content[:800], url))
    return results


# ---------------------------------------------------------------------------
# Ingestion loop
# ---------------------------------------------------------------------------

# All fetchers with their cooldown (seconds between calls)
_FETCHERS = [
    (_fetch_hacker_news,  45,  "hacker_news"),
    (_fetch_devto,        60,  "dev_to"),
    (_fetch_github_issues, 30, "github_issues"),
    (_fetch_github_commits, 25, "github_commits"),
    (_fetch_reddit,       50,  "reddit"),
    (_fetch_stackoverflow, 55, "stackoverflow"),
    (_fetch_arxiv,        90,  "arxiv"),
    (_fetch_wikipedia,    70,  "wikipedia"),
    (_fetch_crossref,     80,  "crossref"),
    (_fetch_pubmed,       85,  "pubmed"),
]

_last_fetch: dict[str, float] = {}


def _score_and_store(domain: str, title: str, text: str, url: str, source: str) -> None:
    """Score a piece of content and add it to the live feed."""
    from slopguard.scoring import score_text

    if len(text.strip()) < 20:
        return

    try:
        result = score_text(text, domain)
        item = LiveItem(
            source=source,
            domain=domain,
            title=title[:120],
            text_preview=text[:200],
            full_text=text,
            score=result.score,
            oversight=result.oversight,
            signals=[s.model_dump() for s in result.signals],
            url=url,
        )
        with _ingestion_lock:
            _live_feed.append(item)
            _ingestion_stats["total_scored"] += 1
            _ingestion_stats["domain_counts"][domain] += 1
            _ingestion_stats["source_counts"][source] += 1
            _ingestion_stats["last_item_at"] = time.time()
            if result.oversight == "low":
                _ingestion_stats["slop_count"] += 1

        # Update analytics
        _update_history_bucket()
        record_pattern_candidates(text, result.score, source)

    except Exception:
        with _ingestion_lock:
            _ingestion_stats["errors"] += 1


def _ingestion_loop() -> None:
    """Main ingestion loop — runs in background thread."""
    with _ingestion_lock:
        _ingestion_stats["started_at"] = time.time()

    while not _stop_event.is_set():
        now = time.time()
        ran_any = False

        for fetcher, cooldown, name in _FETCHERS:
            if _stop_event.is_set():
                break
            last = _last_fetch.get(name, 0)
            if now - last < cooldown:
                continue

            try:
                items = fetcher()
                _last_fetch[name] = time.time()
                with _ingestion_lock:
                    _ingestion_stats["total_ingested"] += len(items)

                for domain, title, text, url in items:
                    if _stop_event.is_set():
                        break
                    _score_and_store(domain, title, text, url, name)
                    time.sleep(0.15)  # don't hammer the scoring engine

                ran_any = True
            except Exception:
                with _ingestion_lock:
                    _ingestion_stats["errors"] += 1

        if not ran_any:
            time.sleep(5)  # all fetchers on cooldown — wait


def start_ingestion() -> None:
    """Start the background ingestion task using asyncio."""
    global _ingestion_task
    import asyncio
    
    if _ingestion_task and not _ingestion_task.done():
        return
        
    _stop_event.clear()
    loop = asyncio.get_event_loop()
    
    # Run the blocking loop in a thread pool managed by asyncio
    _ingestion_task = loop.run_in_executor(None, _ingestion_loop)

def stop_ingestion() -> None:
    """Stop the background ingestion task."""
    _stop_event.set()

def is_running() -> bool:
    return bool(_ingestion_task and not _ingestion_task.done())


# ---------------------------------------------------------------------------
# Analytics helpers — used by /live/worst, /live/leaderboard, /live/history
# ---------------------------------------------------------------------------

# Score history buckets — one entry per minute for the last 60 minutes
_score_history: deque[dict] = deque(maxlen=60)
_last_history_bucket: float = 0.0


def _update_history_bucket() -> None:
    """Called after each scored item — maintains per-minute score history."""
    global _last_history_bucket
    now = time.time()
    bucket_time = now - (now % 60)  # floor to minute

    with _ingestion_lock:
        feed = list(_live_feed)

    if not feed:
        return

    # Items in the current minute
    current_minute_items = [i for i in feed if i.timestamp >= bucket_time]
    if not current_minute_items:
        return

    if bucket_time != _last_history_bucket:
        _last_history_bucket = bucket_time
        slop = sum(1 for i in current_minute_items if i.oversight == "low")
        avg = sum(i.score for i in current_minute_items) / len(current_minute_items)
        _score_history.append({
            "minute": bucket_time,
            "count": len(current_minute_items),
            "avg_score": round(avg, 1),
            "slop_rate": round(slop / len(current_minute_items), 3),
            "slop_count": slop,
        })


def get_worst_items(limit: int = 10) -> list[dict]:
    """Return the lowest-scoring items from the live feed."""
    with _ingestion_lock:
        feed = list(_live_feed)
    sorted_feed = sorted(feed, key=lambda i: i.score)
    return [
        {
            "source": i.source,
            "domain": i.domain,
            "title": i.title,
            "text_preview": i.text_preview,
            "score": i.score,
            "oversight": i.oversight,
            "url": i.url,
            "timestamp": i.timestamp,
            "top_signal": i.signals[0]["name"] if i.signals else "unknown",
            "why_flagged": next(
                (s["reason"] for s in i.signals if s.get("score", 1) < 0.42 and s.get("reason")),
                "Low information density and generic language"
            ),
        }
        for i in sorted_feed[:limit]
    ]


def get_source_leaderboard() -> list[dict]:
    """Rank sources by slop rate — live comparison of HN vs Reddit vs Dev.to etc."""
    with _ingestion_lock:
        feed = list(_live_feed)

    if not feed:
        return []

    by_source: dict[str, list[LiveItem]] = defaultdict(list)
    for item in feed:
        by_source[item.source].append(item)

    rows = []
    for source, items in by_source.items():
        slop = sum(1 for i in items if i.oversight == "low")
        high = sum(1 for i in items if i.oversight == "high")
        avg = sum(i.score for i in items) / len(items)
        rows.append({
            "source": source,
            "total": len(items),
            "avg_score": round(avg, 1),
            "slop_rate": round(slop / len(items), 3),
            "slop_count": slop,
            "high_count": high,
            "slop_pct": round(slop / len(items) * 100, 1),
        })

    return sorted(rows, key=lambda r: r["slop_rate"], reverse=True)


def get_score_history() -> list[dict]:
    """Return per-minute score history for the last 60 minutes."""
    return list(_score_history)


def get_domain_leaderboard() -> list[dict]:
    """Rank domains by average score — which domain has the most slop right now."""
    with _ingestion_lock:
        feed = list(_live_feed)

    if not feed:
        return []

    by_domain: dict[str, list[LiveItem]] = defaultdict(list)
    for item in feed:
        by_domain[item.domain].append(item)

    rows = []
    for domain, items in by_domain.items():
        slop = sum(1 for i in items if i.oversight == "low")
        avg = sum(i.score for i in items) / len(items)
        rows.append({
            "domain": domain,
            "total": len(items),
            "avg_score": round(avg, 1),
            "slop_rate": round(slop / len(items), 3),
            "slop_pct": round(slop / len(items) * 100, 1),
        })

    return sorted(rows, key=lambda r: r["avg_score"])


# ---------------------------------------------------------------------------
# Feedback-driven threshold adaptation
# ---------------------------------------------------------------------------
# When users mark a score as wrong (via /appeals or /feedback),
# the domain threshold shifts slightly using exponential moving average.
# This makes the system learn from human corrections.

_domain_thresholds: dict[str, float] = {
    "code_review": 48.0,
    "docs": 52.0,
    "hiring": 48.0,
    "communications": 45.0,
    "content": 48.0,
    "academia": 48.0,
    "marketplace": 42.0,
    "social_news": 48.0,
    "general": 48.0,
}

_threshold_feedback_log: list[dict] = []


def adapt_threshold(domain: str, was_too_harsh: bool, confidence: float = 1.0) -> dict:
    """Adjust domain threshold based on user feedback.

    was_too_harsh=True  → threshold was too high, lower it (we flagged good content)
    was_too_harsh=False → threshold was too low, raise it (we missed slop)

    Uses exponential moving average: new = 0.95 * old + 0.05 * target
    Max shift per call: ±2 points. Bounds: [30, 70].
    """
    if domain not in _domain_thresholds:
        domain = "general"

    old = _domain_thresholds[domain]
    direction = -1.0 if was_too_harsh else +1.0
    shift = direction * min(2.0, confidence * 2.0)
    new = old * 0.95 + (old + shift) * 0.05
    new = max(30.0, min(70.0, new))
    _domain_thresholds[domain] = round(new, 2)

    entry = {
        "domain": domain,
        "old_threshold": old,
        "new_threshold": round(new, 2),
        "direction": "lowered" if was_too_harsh else "raised",
        "shift": round(new - old, 3),
        "timestamp": time.time(),
    }
    _threshold_feedback_log.append(entry)
    if len(_threshold_feedback_log) > 500:
        del _threshold_feedback_log[:250]

    return entry


def get_current_thresholds() -> dict:
    return dict(_domain_thresholds)


def get_threshold_history(domain: str = "") -> list[dict]:
    if domain:
        return [e for e in _threshold_feedback_log if e["domain"] == domain]
    return list(_threshold_feedback_log)


# ---------------------------------------------------------------------------
# Pattern suggestion queue
# ---------------------------------------------------------------------------
# Novel phrases that appear in low-scoring content get queued.
# After 3+ independent occurrences, they're flagged for addition to the corpus.

_pattern_queue: dict[str, dict] = {}  # phrase → {count, examples, first_seen, last_seen}
_PATTERN_MIN_LENGTH = 8
_PATTERN_MAX_LENGTH = 60
_PROMOTION_THRESHOLD = 3


def _extract_candidate_phrases(text: str, score: float) -> list[str]:
    """Extract candidate slop phrases from low-scoring content."""
    if score >= 48:
        return []  # only extract from slop

    candidates = []

    # Multi-word phrases 2-6 words that look like AI patterns
    words = text.lower().split()
    for n in range(2, 7):
        for i in range(len(words) - n + 1):
            phrase = " ".join(words[i:i+n])
            if len(phrase) < _PATTERN_MIN_LENGTH or len(phrase) > _PATTERN_MAX_LENGTH:
                continue
            # Skip phrases with numbers (too specific)
            if any(c.isdigit() for c in phrase):
                continue
            # Skip phrases that are already in the known slop corpus
            from slopguard.detectors.specificity import _AI_SLOP_PATTERNS
            if _AI_SLOP_PATTERNS.search(phrase):
                continue
            # Only keep phrases that sound like AI filler
            filler_words = {
                "ensure", "enhance", "improve", "robust", "seamless", "leverage",
                "comprehensive", "innovative", "streamline", "empower", "harness",
                "cutting-edge", "state-of-the-art", "best practices", "going forward",
                "moving forward", "in today", "crucial role", "key aspect",
                "various aspects", "overall", "effectively", "efficiently",
            }
            if any(fw in phrase for fw in filler_words):
                candidates.append(phrase)

    return candidates[:5]  # max 5 candidates per item


def record_pattern_candidates(text: str, score: float, source: str = "") -> None:
    """Extract and queue candidate slop phrases from a scored item."""
    candidates = _extract_candidate_phrases(text, score)
    now = time.time()

    for phrase in candidates:
        if phrase not in _pattern_queue:
            _pattern_queue[phrase] = {
                "phrase": phrase,
                "count": 0,
                "examples": [],
                "first_seen": now,
                "last_seen": now,
                "sources": [],
                "promoted": False,
            }
        entry = _pattern_queue[phrase]
        entry["count"] += 1
        entry["last_seen"] = now
        if source and source not in entry["sources"]:
            entry["sources"].append(source)
        if len(entry["examples"]) < 3:
            entry["examples"].append(text[:100])


def get_pattern_queue(promoted_only: bool = False) -> list[dict]:
    """Return queued patterns sorted by occurrence count."""
    items = list(_pattern_queue.values())
    if promoted_only:
        items = [i for i in items if i["count"] >= _PROMOTION_THRESHOLD]
    return sorted(items, key=lambda x: x["count"], reverse=True)[:50]


def promote_pattern(phrase: str) -> bool:
    """Mark a pattern as promoted (manually approved for corpus addition)."""
    if phrase in _pattern_queue:
        _pattern_queue[phrase]["promoted"] = True
        return True
    return False
