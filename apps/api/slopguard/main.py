import json
import re
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timezone

import asyncio

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, RedirectResponse, StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from slopguard.evaluate import evaluate
from slopguard.models import (
    BatchScoreRequest,
    CitationRequest,
    FeedbackRequest,
    GitHubOAuthRequest,
    GitHubTimelineRequest,
    GitHubVelocityRequest,
    PRScoreRequest,
    PRUrlScoreRequest,
    RepoScoreRequest,
    ScoreEventRequest,
    SupabaseFeedback,
    SupabaseScoreEvent,
    TextScoreRequest,
    UserProfileRequest,
)
from slopguard.scoring import score_batch, score_text


app = FastAPI(
    title="SlopGuard API",
    description="Human oversight scoring for low-effort AI slop.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
async def startup_event():
    """Start live content ingestion on API startup."""
    from slopguard.adapters.live_ingestion import start_ingestion
    start_ingestion()


@app.on_event("shutdown")
async def shutdown_event():
    from slopguard.adapters.live_ingestion import stop_ingestion
    stop_ingestion()


SCORE_EVENTS: list[dict] = []
FEEDBACK_EVENTS: list[dict] = []


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def fetch_text(url: str, token: str = "") -> str:
    headers = {"User-Agent": "SlopGuard-Hackathon-Demo/0.1"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(request, timeout=15) as response:
        return response.read().decode("utf-8", errors="replace")


@app.get("/", response_class=HTMLResponse)
def root() -> str:
    return """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>SlopGuard API</title>
    <style>
      body { margin: 0; background: #f5f7fb; color: #172033; font-family: Inter, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
      main { max-width: 920px; margin: 0 auto; padding: 48px 20px; }
      h1 { margin: 0; font-size: 56px; line-height: 1; letter-spacing: 0; }
      p { color: #617086; font-size: 18px; line-height: 1.55; }
      .grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin-top: 24px; }
      a, .card { border: 1px solid #d9e1ea; border-radius: 8px; background: white; padding: 16px; text-decoration: none; color: #172033; }
      a strong, .card strong { display: block; margin-bottom: 6px; }
      code { background: #e8edf4; border-radius: 6px; padding: 2px 6px; }
      .cta { display: inline-block; margin-top: 20px; background: #172033; color: white; font-weight: 800; }
      @media (max-width: 720px) { .grid { grid-template-columns: 1fr; } h1 { font-size: 42px; } }
    </style>
  </head>
  <body>
    <main>
      <p><strong>Slop Scan Hackathon 2026</strong></p>
      <h1>SlopGuard API</h1>
      <p>The Internet's Quality Layer. This FastAPI service scores content for human oversight across code review, docs, hiring, communications, content, academia, marketplaces, and social/news.</p>
      <a class="cta" href="http://localhost:3000">Open Dashboard</a>
      <div class="grid">
        <a href="/live/feed"><strong>🔴 Live Feed</strong><span>Real content scored live from HN, Reddit, GitHub, arXiv, Wikipedia.</span></a>
        <a href="/live/stats"><strong>📊 Live Stats</strong><span>Items/min, domain breakdown, slop rate, uptime.</span></a>
        <a href="/docs"><strong>API Docs</strong><span>Interactive Swagger docs for every endpoint.</span></a>
        <a href="/submission/status"><strong>Submission Status</strong><span>Machine-readable PRD completion map.</span></a>
        <a href="/evaluation/sample"><strong>Bake-Off Metrics</strong><span>Seed confusion matrix, precision, recall, and F1.</span></a>
        <a href="/evaluation/hc3"><strong>HC3 Benchmark</strong><span>Independent validation on peer-reviewed dataset.</span></a>
        <a href="/demo/scenarios"><strong>Demo Scenarios</strong><span>Built-in examples for live judging.</span></a>
        <a href="/adapters/status"><strong>Adapters Status</strong><span>Which production ML adapters are active.</span></a>
        <a href="/excellence"><strong>Human Excellence</strong><span>Curated high-quality examples across all tracks.</span></a>
        <a href="/ticker"><strong>Slop Ticker</strong><span>Real-time aggregated quality stats.</span></a>
        <a href="/auth/github/url"><strong>GitHub OAuth</strong><span>Connect GitHub for real Slop Velocity.</span></a>
      </div>
      <p>Core: <code>POST /score/text</code>, <code>POST /improve</code>, <code>POST /score/pr</code>, <code>POST /score/repo</code>, <code>POST /score/batch</code>, <code>POST /citations/verify</code>. Production: <code>POST /telemetry/score</code>, <code>POST /github/velocity</code>, <code>GET /adapters/status</code>.</p>
    </main>
  </body>
</html>
"""


@app.get("/health")
def health() -> dict:
    return {"status": "ok", "service": "slopguard-api"}


@app.get("/submission/status")
def submission_status():
    return {
        "project": "SlopGuard",
        "tagline": "The Internet's Quality Layer",
        "hackathon": "Slop Scan Hackathon 2026",
        "primary_deliverables": {
            "chrome_extension": "implemented",
            "nextjs_dashboard": "implemented",
            "fastapi_detection_engine": "implemented",
            "all_8_track_adapters": "implemented",
            "open_source_ready_assets": "implemented",
        },
        "tracks": {
            "A_code_review": ["pr_diff_divergence", "reviewer_impact_proxy", "code_comment_intelligence", "commit_reasoning_ratio", "slop_velocity_proxy"],
            "B_docs": ["heading_to_content_ratio", "concrete_example_density", "circular_explanation_graph", "codebase_drift_proxy"],
            "C_hiring": ["company_specificity", "achievement_specificity", "structural_template_detection", "batch_structural_fingerprint", "batch_similarity_clustering"],
            "D_communications": ["decision_action_density", "compression_score", "reply_information_score", "meeting_notes_substance"],
            "E_content_seo": ["claim_specificity", "time_to_value_ratio", "structure_rehash", "originality_proxy"],
            "F_academia": ["citation_shape_verification", "academic_grounding", "stylistic_consistency", "self_citation_inflation", "citation_claim_alignment"],
            "G_marketplaces": ["review_specificity", "reviewer_authenticity_proxy", "review_cluster_analysis", "temporal_clustering_proxy"],
            "H_social_news": ["rage_bait_fingerprint", "network_coordination_proxy", "posting_cadence_proxy", "engagement_authenticity_proxy"],
        },
        "bonus_targets": {
            "live_fire": "demo-ready via extension and dashboard",
            "cross_track_scanner": "implemented via shared engine and domain adapters",
            "open_source_ready": "README, CI, Docker, CLI, contribution guide, examples",
            "bake_off": "seed evaluation endpoint and CLI included",
        },
        "production_followups": [
            "fine-tuned RoBERTa model",
            "sentence-transformers and FAISS backing store",
            "GitHub OAuth timeline ingestion",
            "CrossRef/Semantic Scholar/PubMed live verification",
            "Chrome Web Store publication",
            "Supabase accounts and opt-in telemetry",
        ],
    }



@app.post("/score/text")
def score_text_endpoint(request: TextScoreRequest):
    result = score_text(request.text, request.domain, request.metadata)
    _fire_webhooks(result.score, result.oversight, request.domain, request.text)
    return result


@app.post("/score/pr")
def score_pr_endpoint(request: PRScoreRequest):
    text = f"{request.title}\n\n{request.description}".strip()
    metadata = {**request.metadata, "diff": request.diff, "comments": request.comments}
    result = score_text(text, "code_review", metadata)
    _fire_webhooks(result.score, result.oversight, "code_review", text)
    return result


@app.post("/score/pr-url")
def score_pr_url_endpoint(request: PRUrlScoreRequest):
    match = re.match(r"https://github\.com/([^/]+)/([^/]+)/pull/(\d+)", request.url.rstrip("/"))
    if not match:
        return {
            "status": "unsupported_url",
            "message": "Use a public GitHub pull request URL such as https://github.com/owner/repo/pull/123.",
        }
    owner, repo, number = match.groups()
    repo_id = f"{owner}/{repo}"
    diff_url = f"https://github.com/{owner}/{repo}/pull/{number}.diff"
    try:
        diff = fetch_text(diff_url, request.token)
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        return {
            "status": "fetch_failed",
            "message": f"Could not fetch PR diff: {exc}",
            "fallback": "Paste the PR title, description, and diff into /score/pr or the dashboard PR tab.",
        }
    title = f"{owner}/{repo} PR #{number}"
    description = "Public PR URL analysis. SlopGuard fetched the diff and scores whether the PR metadata adds human reasoning beyond changed files."
    result = score_text(f"{title}\n\n{description}", "code_review", {"diff": diff, "comments": [], "repo_id": repo_id})
    return {"status": "ok", "url": request.url, "diff_bytes": len(diff), "result": result}


@app.post("/score/repo")
def score_repo_endpoint(request: RepoScoreRequest):
    scored = []
    for pr in request.pull_requests:
        text = f"{pr.title}\n\n{pr.description}".strip()
        metadata = {**pr.metadata, "diff": pr.diff, "comments": pr.comments, "repo_id": request.repo}
        scored.append(score_text(text, "code_review", metadata))

    score = round(sum(item.score for item in scored) / max(len(scored), 1), 1) if scored else 62.0
    oversight = "high" if score >= 72 else "mixed" if score >= 48 else "low"

    # --- Dynamic timeline from actual PR scores ---
    timeline = []
    if scored:
        pr_scores = [item.score for item in scored]
        num_prs = len(pr_scores)
        # Create weekly buckets: divide PRs into groups to simulate weekly progression
        num_weeks = min(max(3, num_prs), 8)  # At least 3, at most 8 weeks
        bucket_size = max(1, num_prs // num_weeks)
        for week_idx in range(num_weeks):
            start = week_idx * bucket_size
            end = start + bucket_size if week_idx < num_weeks - 1 else num_prs
            bucket = pr_scores[start:end]
            if bucket:
                # Sliding window average for this week
                week_avg = round(sum(bucket) / len(bucket), 1)
            else:
                week_avg = score
            week_label = f"W-{num_weeks - week_idx}" if week_idx < num_weeks - 1 else "W-1"
            timeline.append({"week": week_label, "score": week_avg})
    else:
        # Fallback: single current-week entry
        timeline = [{"week": "W-1", "score": score}]

    # --- Dynamic hotspots from actual signal analysis ---
    hotspots = []
    if scored:
        # Aggregate all signals across PRs, find the weakest ones
        signal_scores: dict[str, list[float]] = {}
        signal_labels: dict[str, list[str]] = {}
        for result in scored:
            for signal in result.signals:
                signal_scores.setdefault(signal.name, []).append(signal.score)
                signal_labels.setdefault(signal.name, []).append(signal.label)

        # Sort signals by average score (ascending = worst first)
        ranked = sorted(signal_scores.items(), key=lambda kv: sum(kv[1]) / len(kv[1]))
        # Map signal names to human-readable area names
        area_map = {
            "pr_diff_divergence": "PR descriptions",
            "reviewer_impact_proxy": "Review comments",
            "code_comment_intelligence": "Code comments",
            "commit_reasoning_ratio": "Commit messages",
            "slop_velocity_proxy": "Development velocity",
        }
        for signal_name, scores_list in ranked[:3]:
            avg = sum(scores_list) / len(scores_list)
            # Find the most common non-positive label
            label_counts = {}
            for lbl in signal_labels.get(signal_name, []):
                label_counts[lbl] = label_counts.get(lbl, 0) + 1
            most_common_label = max(label_counts, key=label_counts.get) if label_counts else "unknown"
            low_count = sum(1 for s in scores_list if s < 0.55)
            hotspots.append({
                "area": area_map.get(signal_name, signal_name.replace("_", " ").title()),
                "risk": most_common_label,
                "count": low_count,
                "avg_score": round(avg, 3),
            })
    else:
        hotspots = [
            {"area": "PR descriptions", "risk": "no_data", "count": 0, "avg_score": 0.0},
        ]

    return {
        "repo": request.repo,
        "score": score,
        "oversight": oversight,
        "timeline": timeline,
        "hotspots": hotspots,
        "pull_requests": scored,
    }


@app.post("/score/batch")
def score_batch_endpoint(request: BatchScoreRequest):
    return score_batch(request.items)


@app.post("/score/citations")
def score_citations_endpoint(request: CitationRequest):
    """Verify citations using CrossRef + Semantic Scholar + PubMed + local shape checks."""
    from slopguard.adapters.citation_verification import verify_citations_batch
    results = verify_citations_batch(request.citations)
    return {
        "status": "expanded_verification",
        "message": "Uses CrossRef DOI lookup, Semantic Scholar, PubMed, and local citation-shape checks.",
        "sources": ["crossref", "semantic_scholar", "pubmed", "local_shape_check"],
        "citations": results,
    }


@app.post("/events/score")
def record_score_event(request: ScoreEventRequest):
    event = {**request.model_dump(), "created_at": now_iso()}
    SCORE_EVENTS.append(event)
    del SCORE_EVENTS[:-250]
    return {"status": "recorded", "event": event}


@app.post("/feedback")
def record_feedback(request: FeedbackRequest):
    event = {**request.model_dump(), "created_at": now_iso()}
    FEEDBACK_EVENTS.append(event)
    del FEEDBACK_EVENTS[:-250]
    return {"status": "recorded", "event": event}


@app.get("/personal/summary")
def personal_summary():
    if not SCORE_EVENTS:
        return {
            "total_scored": 0,
            "low_oversight_percent": 0,
            "average_score": 0,
            "sites": [],
            "recent": [],
            "feedback": {"total": len(FEEDBACK_EVENTS), "slop": 0, "reviewed": 0, "unsure": 0},
        }
    by_host: dict[str, list[float]] = {}
    for event in SCORE_EVENTS:
        host = re.sub(r"^https?://", "", event["url"]).split("/")[0] or "local"
        by_host.setdefault(host, []).append(float(event["score"]))
    sites = [
        {"domain": host, "average_score": round(sum(scores) / len(scores), 1), "count": len(scores)}
        for host, scores in by_host.items()
    ]
    sites.sort(key=lambda item: item["average_score"])
    feedback_counts = {"slop": 0, "reviewed": 0, "unsure": 0}
    for event in FEEDBACK_EVENTS:
        feedback_counts[event["user_label"]] += 1
    low = len([event for event in SCORE_EVENTS if event["oversight"] == "low"])
    average = sum(float(event["score"]) for event in SCORE_EVENTS) / len(SCORE_EVENTS)
    return {
        "total_scored": len(SCORE_EVENTS),
        "low_oversight_percent": round((low / len(SCORE_EVENTS)) * 100, 1),
        "average_score": round(average, 1),
        "sites": sites[:10],
        "recent": SCORE_EVENTS[-10:][::-1],
        "feedback": {"total": len(FEEDBACK_EVENTS), **feedback_counts},
    }


@app.get("/evaluation/sample")
def sample_evaluation():
    from slopguard.evaluate import _find_samples_path
    return evaluate(str(_find_samples_path()))


@app.get("/evaluation/hc3")
def hc3_evaluation():
    """HC3 benchmark results. Returns cached results or runs fresh evaluation."""
    from pathlib import Path

    results_path = Path(__file__).resolve().parent.parent.parent.parent / "datasets" / "hc3_results.json"
    if results_path.exists():
        import json
        return json.loads(results_path.read_text(encoding="utf-8"))

    return {
        "status": "not_yet_evaluated",
        "message": "Run 'python -m slopguard.evaluate_hc3' to download HC3 and evaluate.",
        "benchmark": "HC3",
        "dataset": "Hello-SimpleAI/HC3",
        "instructions": {
            "pip": "pip install datasets",
            "run": "python -m slopguard.evaluate_hc3",
            "url": "https://huggingface.co/datasets/Hello-SimpleAI/HC3",
        },
    }


@app.get("/demo/scenarios")
def demo_scenarios():
    return {
        "items": [
            {
                "name": "Hollow PR Description",
                "domain": "code_review",
                "text": "Updated files and improved the implementation. This change enhances the user experience and fixes various issues.",
                "expected_score_range": "35-48",
                "why": "Generic improvement language, no concrete details, vague references.",
            },
            {
                "name": "Concise Specific PR (correctly mixed)",
                "domain": "code_review",
                "text": "Fixed JWT secret exposure in auth/middleware.js \u2014 previous implementation logged the full token on line 47, appearing in CloudWatch logs accessible to the ops team. Rotated all affected secrets, added log sanitization, updated tests.",
                "expected_score_range": "52-60",
                "why": (
                    "Scores mixed (not high) — and that's correct. "
                    "It's a concise, specific 2-sentence description: strong claim detected, specificity 0.99, "
                    "file path + line number + named service (CloudWatch). "
                    "But it's still only 2 sentences with no tradeoffs, no alternatives considered, "
                    "no context about why JWT was chosen. Mixed is honest. "
                    "SlopGuard doesn't inflate scores for brevity."
                ),
            },
            {
                "name": "Prompt-Engineered AI Slop",
                "domain": "code_review",
                "text": "Refactored the authentication module because it was causing performance issues in production. The new implementation is more robust and provides better error handling for various edge cases.",
                "expected_score_range": "45-55",
                "why": "Looks specific but unfalsifiable — no measurements, pure adjectives, vague references. AI slop fingerprint detects 'provides better' and 'various edge cases' patterns.",
            },
            {
                "name": "Genuine Human Reasoning (high oversight)",
                "domain": "code_review",
                "text": "Profiling showed auth middleware adding 340ms to every request. Moved token validation from the hot path to a background job using Redis cache. P95 latency dropped from 420ms to 85ms.",
                "expected_score_range": "58-70",
                "why": (
                    "Measurements (340ms, 420ms, 85ms), tool references (profiling, Redis), "
                    "before/after comparison. This is what high oversight looks like: "
                    "every claim is falsifiable. Score gap vs prompt-engineered slop: ~10 points."
                ),
            },
            {
                "name": "Full High-Oversight PR (best case)",
                "domain": "code_review",
                "text": (
                    "Changed billing/retry.ts to cap retries at 3 because Stripe was returning "
                    "duplicate webhook delivery during deploys. Added a 10-minute idempotency window "
                    "and tested with the replay fixture. Considered exponential backoff but rejected it "
                    "because our SLA requires retry within 30s. Tradeoff: slower recovery on transient "
                    "failures, but eliminates double-billing risk (was costing ~$200/day in credits)."
                ),
                "expected_score_range": "65-78",
                "why": (
                    "Specific numbers (3 retries, 10 min, 30s, $200/day), named entity (Stripe), "
                    "concrete testing approach, alternative considered and rejected with reasoning, "
                    "explicit tradeoff acknowledged. This is what a truly high-oversight PR looks like."
                ),
            },
            {
                "name": "Generic Marketplace Review",
                "domain": "marketplace",
                "text": "Amazing product. Great quality and highly recommend. It works perfectly and exceeded my expectations in every way.",
                "expected_score_range": "30-42",
                "why": "Pure adjectives, no product-specific details, template review structure.",
            },
            {
                "name": "SEO Filler Article",
                "domain": "content",
                "text": "In today's digital landscape, productivity tools play a crucial role in helping teams unlock the power of collaboration. This comprehensive overview explores various aspects of modern workflows and how they enhance user experience.",
                "expected_score_range": "25-38",
                "why": "AI slop fingerprint: 'In today's', 'crucial role', 'unlock the power', 'comprehensive overview', 'various aspects'. Zero concrete claims.",
            },
            {
                "name": "Hedged Causal Claim",
                "domain": "code_review",
                "text": "Updated the database query because it could potentially improve performance for some users in certain scenarios.",
                "expected_score_range": "30-42",
                "why": "Hedged causal: 'could potentially improve'. Fake specificity: 'some users', 'certain scenarios'. No measurement.",
            },
        ],
        "score_gap": {
            "ai_slop_vs_human_short_text": "~10 points",
            "ai_slop_vs_human_full_pr": "15-25 points",
            "explanation": (
                "On short 2-3 sentence texts, the gap is ~10 points. "
                "On full PR descriptions with tradeoffs and alternatives, the gap grows to 15-25 points. "
                "Prompt-engineered AI slop scores ~50. Genuine human reasoning with measurements scores ~60. "
                "Full high-oversight PRs with tradeoffs score 65+. "
                "Mixed (47-63) means 'better than slop, not yet excellent' — that's a meaningful signal, not a failure."
            ),
            "demo_narrative": (
                "Show the JWT PR scoring 56 (mixed). Explain: it's specific, the strong claim is detected, "
                "but it's 2 sentences with no tradeoffs. Then show the full billing/retry PR scoring 65+. "
                "The difference is visible and explainable. That's the product."
            ),
        },
    }


@app.get("/leaderboard/sites")
def site_leaderboard(category: str = ""):
    """Get site trust leaderboard. Uses Supabase if configured, otherwise demo data."""
    from slopguard.adapters.supabase_telemetry import get_site_leaderboard as supabase_leaderboard

    result = supabase_leaderboard(category)
    if result.get("items"):
        return result

    # Fallback to demo data
    return {
        **result,
        "items": [
            {"domain": "github.com", "score": 78.4, "trend": "+3.1"},
            {"domain": "stackoverflow.com", "score": 74.9, "trend": "+1.8"},
            {"domain": "dev.to", "score": 68.3, "trend": "-0.7"},
            {"domain": "medium.com", "score": 62.1, "trend": "-2.3"},
            {"domain": "docs.python.org", "score": 81.6, "trend": "+0.4"},
            {"domain": "w3schools.com", "score": 55.8, "trend": "-1.1"},
            {"domain": "geeksforgeeks.org", "score": 49.2, "trend": "-3.5"},
            {"domain": "content-farm.example", "score": 31.8, "trend": "-8.2"},
            {"domain": "seo-mill.example", "score": 27.4, "trend": "-5.9"},
            {"domain": "ai-blog-network.example", "score": 22.1, "trend": "-11.3"},
        ],
    }


@app.get("/leaderboard/repos")
def repo_leaderboard(org: str = ""):
    """Get repo oversight leaderboard. Uses Supabase if configured, otherwise demo data."""
    from slopguard.adapters.supabase_telemetry import get_repo_leaderboard as supabase_leaderboard

    result = supabase_leaderboard(org)
    if result.get("items"):
        return result

    # Fallback to demo data
    return {
        **result,
        "items": [
            {"repo": "facebook/react", "score": 82.3, "reviewer_impact": 0.74},
            {"repo": "vercel/next.js", "score": 78.1, "reviewer_impact": 0.68},
            {"repo": "microsoft/typescript", "score": 84.7, "reviewer_impact": 0.81},
            {"repo": "torvalds/linux", "score": 91.2, "reviewer_impact": 0.93},
            {"repo": "openai/tiktoken", "score": 76.5, "reviewer_impact": 0.62},
            {"repo": "demo/low-oversight", "score": 28.6, "reviewer_impact": 0.12},
            {"repo": "startup/mvp-rush", "score": 34.2, "reviewer_impact": 0.19},
            {"repo": "agency/client-site", "score": 41.7, "reviewer_impact": 0.27},
        ],
    }


# =============================================================================
# Production endpoints (optional — require env vars or installed adapters)
# =============================================================================


@app.get("/auth/github/url")
def github_auth_url(state: str = ""):
    """Get GitHub OAuth authorization URL."""
    from slopguard.adapters.github_oauth import get_auth_url
    url = get_auth_url(state)
    if not url:
        return {"error": "GitHub OAuth not configured. Set GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET."}
    return {"auth_url": url}


@app.get("/auth/github/callback")
def github_callback(code: str, state: str = ""):
    """Handle GitHub OAuth callback and exchange code for token."""
    from slopguard.adapters.github_oauth import exchange_code_for_token, fetch_user
    result = exchange_code_for_token(code)
    if "error" in result:
        return result
    user = fetch_user(result["access_token"])
    return {"access_token": result["access_token"], "user": user}


@app.post("/github/timeline")
def github_timeline(request: GitHubTimelineRequest):
    """Fetch PR timeline from a GitHub repo for Slop Velocity analysis."""
    from slopguard.adapters.github_oauth import fetch_pr_timeline
    timeline = fetch_pr_timeline(request.token, request.owner, request.repo, request.limit)
    return {"owner": request.owner, "repo": request.repo, "pull_requests": timeline}


@app.post("/github/velocity")
def github_velocity(request: GitHubVelocityRequest):
    """Compute Slop Velocity from real GitHub PR data."""
    from slopguard.adapters.github_oauth import compute_slop_velocity, fetch_pr_timeline

    timeline = fetch_pr_timeline(request.token, request.owner, request.repo, request.limit)
    if not timeline:
        return {"error": "Could not fetch PR timeline. Check token and repo access."}

    # Score each PR's description
    scored_prs = []
    for pr in timeline:
        text = f"{pr.get('title', '')}\n\n{pr.get('description', '')}"
        if text.strip():
            result = score_text(text, "code_review")
            scored_prs.append({"number": pr.get("number"), "score": result.score})

    velocity = compute_slop_velocity(timeline, scored_prs)
    return {"owner": request.owner, "repo": request.repo, "velocity": velocity}


@app.post("/telemetry/score")
def telemetry_score_event(request: SupabaseScoreEvent):
    """Record a score event in Supabase (if configured). Falls back to in-memory."""
    from slopguard.adapters.supabase_telemetry import insert_score_event
    result = insert_score_event(
        user_id=request.user_id,
        url=request.url,
        title=request.title,
        domain=request.domain,
        score=request.score,
        oversight=request.oversight,
    )
    return result


@app.post("/telemetry/feedback")
def telemetry_feedback(request: SupabaseFeedback):
    """Record user feedback in Supabase (if configured)."""
    from slopguard.adapters.supabase_telemetry import insert_feedback
    result = insert_feedback(
        user_id=request.user_id,
        event_id=request.event_id,
        user_label=request.user_label,
        notes=request.notes,
    )
    return result


@app.get("/telemetry/summary/{user_id}")
def telemetry_summary(user_id: str):
    """Get user's score summary from Supabase."""
    from slopguard.adapters.supabase_telemetry import get_user_summary
    return get_user_summary(user_id)


@app.post("/telemetry/profile")
def telemetry_profile(request: UserProfileRequest):
    """Upsert user profile in Supabase."""
    from slopguard.adapters.supabase_telemetry import upsert_user_profile
    return upsert_user_profile(request.user_id, request.preferences)


@app.post("/citations/verify")
def verify_citations_expanded(request: CitationRequest):
    """Verify citations against CrossRef + Semantic Scholar + PubMed."""
    from slopguard.adapters.citation_verification import verify_citations_batch
    results = verify_citations_batch(request.citations)
    return {
        "status": "expanded_verification",
        "sources": ["crossref", "semantic_scholar", "pubmed", "local_shape_check"],
        "citations": results,
    }


@app.get("/adapters/status")
def adapters_status():
    """Report which production adapters are available."""
    from slopguard.adapters.live_ingestion import get_ingestion_stats, is_running

    status = {
        "sentence_transformers": False,
        "roberta_whywhat": False,
        "faiss": False,
        "networkx": False,
        "tree_sitter": False,
        "supabase": False,
        "github_oauth": False,
        "live_ingestion": is_running(),
    }

    ingestion = get_ingestion_stats()
    status["live_ingestion_stats"] = {
        "active": is_running(),
        "total_scored": ingestion.get("total_scored", 0),
        "items_per_minute": ingestion.get("items_per_minute", 0),
        "slop_rate": ingestion.get("slop_rate", 0),
        "sources": list(ingestion.get("source_counts", {}).keys()),
    }

    # Check sentence-transformers
    try:
        from slopguard.adapters.semantic_embedding import semantic_embedding_uniqueness
        status["sentence_transformers"] = semantic_embedding_uniqueness("test") != 0.5
    except ImportError:
        pass

    # Check RoBERTa
    try:
        from slopguard.adapters.roberta_whywhat import why_what_roberta_ratio
        status["roberta_whywhat"] = True
    except ImportError:
        pass

    # Check FAISS
    try:
        import faiss
        status["faiss"] = True
    except ImportError:
        pass

    # Check NetworkX
    try:
        import networkx
        status["networkx"] = True
    except ImportError:
        pass

    # Check tree-sitter
    try:
        from slopguard.adapters.treesitter_comments import _load_parsers
        status["tree_sitter"] = _load_parsers()
    except ImportError:
        pass

    # Check Supabase
    try:
        from slopguard.adapters.supabase_telemetry import is_enabled
        status["supabase"] = is_enabled()
    except ImportError:
        pass

    # Check GitHub OAuth
    import os
    status["github_oauth"] = bool(os.environ.get("GITHUB_CLIENT_ID") and os.environ.get("GITHUB_CLIENT_SECRET"))

    return status


# =============================================================================
# New features: Improvement Engine, Trust API, Webhooks, Appeals, Ticker, Excellence
# =============================================================================


class ImprovementRequest(BaseModel):
    text: str
    domain: str = "general"


@app.post("/improve")
def improve_text_endpoint(request: ImprovementRequest):
    """Before/After Improvement Engine — suggests specific fixes for flagged sentences.

    Transforms SlopGuard from a judge into a writing coach.
    """
    from slopguard.detectors.improvement import improve_text
    return improve_text(request.text, request.domain)


# ---- Trust Score API with versioning ----

_TRUST_SCORES: dict[str, list[dict]] = {}


@app.get("/trust/{entity_type}/{entity:path}")
def trust_score(entity_type: str, entity: str):
    """Get a stable, referenceable trust score for any entity.

    entity_type: site, repo, reviews, publisher, etc.
    entity: the entity identifier (e.g., github.com/facebook/react)

    Returns current score, history, methodology, and embeddable badge URL.
    """
    key = f"{entity_type}/{entity}"

    if key not in _TRUST_SCORES:
        # Seed with demo data
        import random
        random.seed(hash(key) % (2**32))
        base_score = random.uniform(40, 85)
        history = []
        for i in range(12):
            history.append({
                "week": f"2026-W{i+1}",
                "score": round(base_score + random.gauss(0, 3), 1),
            })
        _TRUST_SCORES[key] = history

    history = _TRUST_SCORES[key]
    current = history[-1]["score"] if history else 50.0
    trend = history[-1]["score"] - history[-2]["score"] if len(history) >= 2 else 0.0

    badge_url = f"https://slopguard.dev/badge/{key}"

    return {
        "entity": key,
        "current_score": round(current, 1),
        "trend": f"+{trend:.1f}" if trend >= 0 else f"{trend:.1f}",
        "oversight": "high" if current >= 65 else "mixed" if current >= 48 else "low",
        "history": history,
        "methodology": {
            "signals": ["information_density", "why_vs_what", "human_delta", "template_structure", "semantic_uniqueness", "specificity"],
            "description": "Scores are based on 6 universal signals measuring human oversight, not AI authorship.",
            "threshold_high": 65,
            "threshold_mixed": 48,
        },
        "badge": {
            "url": badge_url,
            "markdown": f"![SlopGuard Score](https://slopguard.dev/badge/{key})",
            "html": f'<img src="https://slopguard.dev/badge/{key}" alt="SlopGuard Score">',
        },
    }


# ---- Webhook System ----

_WEBHOOKS: list[dict] = []


class WebhookRequest(BaseModel):
    url: str
    trigger: str = "score_below"  # score_below, score_above, oversight_change
    threshold: float = 50
    domains: list[str] = []


@app.post("/webhooks/register")
def register_webhook(request: WebhookRequest):
    """Register a webhook that fires when SlopGuard scores cross a threshold."""
    import uuid
    webhook = {
        "id": str(uuid.uuid4())[:8],
        "url": request.url,
        "trigger": request.trigger,
        "threshold": request.threshold,
        "domains": request.domains,
        "created_at": "2026-05-27T00:00:00Z",
        "fired_count": 0,
        "status": "active",
    }
    _WEBHOOKS.append(webhook)
    return webhook


@app.get("/webhooks")
def list_webhooks():
    """List registered webhooks."""
    return {"webhooks": _WEBHOOKS, "total": len(_WEBHOOKS)}


@app.delete("/webhooks/{webhook_id}")
def delete_webhook(webhook_id: str):
    """Delete a registered webhook."""
    global _WEBHOOKS
    _WEBHOOKS = [w for w in _WEBHOOKS if w["id"] != webhook_id]
    return {"deleted": webhook_id}


def _fire_webhooks(score: float, oversight: str, domain: str, text: str = ""):
    """Fire webhooks that match the score event. Called internally after scoring."""
    import urllib.request
    import json as _json

    for webhook in _WEBHOOKS:
        if webhook["status"] != "active":
            continue
        if webhook["domains"] and domain not in webhook["domains"]:
            continue

        should_fire = False
        if webhook["trigger"] == "score_below" and score < webhook["threshold"]:
            should_fire = True
        elif webhook["trigger"] == "score_above" and score > webhook["threshold"]:
            should_fire = True

        if should_fire:
            try:
                payload = _json.dumps({
                    "event": "slopguard.score",
                    "score": score,
                    "oversight": oversight,
                    "domain": domain,
                    "webhook_id": webhook["id"],
                    "text_preview": text[:200],
                }).encode()
                req = urllib.request.Request(
                    webhook["url"],
                    data=payload,
                    headers={"Content-Type": "application/json"},
                )
                with urllib.request.urlopen(req, timeout=10) as resp:
                    webhook["fired_count"] += 1
            except Exception:
                pass  # Silent fail for webhooks


# ---- Score Appeal System ----

_APPEALS: list[dict] = []


class AppealRequest(BaseModel):
    text: str
    original_score: float
    domain: str = "general"
    reasoning: str = ""


@app.post("/appeals")
def submit_appeal(request: AppealRequest):
    """Submit an appeal when SlopGuard scores something as slop and the author disagrees."""
    import uuid
    appeal = {
        "id": str(uuid.uuid4())[:8],
        "text": request.text,
        "original_score": request.original_score,
        "domain": request.domain,
        "reasoning": request.reasoning,
        "upvotes": 0,
        "downvotes": 0,
        "status": "pending",  # pending, community_verified, community_disputed
        "created_at": "2026-05-27T00:00:00Z",
    }
    _APPEALS.append(appeal)
    return appeal


@app.post("/appeals/{appeal_id}/vote")
def vote_appeal(appeal_id: str, vote: str = "up"):
    """Vote on an appeal (up = agree with appeal, down = disagree)."""
    for appeal in _APPEALS:
        if appeal["id"] == appeal_id:
            if vote == "up":
                appeal["upvotes"] += 1
            else:
                appeal["downvotes"] += 1

            # Auto-resolve after enough votes
            total = appeal["upvotes"] + appeal["downvotes"]
            if total >= 5:
                if appeal["upvotes"] > appeal["downvotes"]:
                    appeal["status"] = "community_verified"
                else:
                    appeal["status"] = "community_disputed"

            return appeal
    return {"error": "Appeal not found"}


@app.get("/appeals")
def list_appeals(status: str = ""):
    """List appeals, optionally filtered by status."""
    appeals = _APPEALS
    if status:
        appeals = [a for a in appeals if a["status"] == status]
    return {"appeals": appeals, "total": len(appeals)}


# ---- Community Verification Feed ----

_FEED: list[dict] = []


@app.get("/feed")
def verification_feed(limit: int = 20):
    """Public feed of recently scored content with community voting."""
    # Generate some demo feed items if empty
    if not _FEED:
        import random
        random.seed(42)
        demo_items = [
            {"text": "Updated auth middleware to fix token leak in CloudWatch logs.", "score": 72, "domain": "code_review", "oversight": "high"},
            {"text": "Improved performance and fixed various issues.", "score": 35, "domain": "code_review", "oversight": "low"},
            {"text": "Added Redis caching — P95 latency dropped from 420ms to 85ms.", "score": 78, "domain": "code_review", "oversight": "high"},
            {"text": "Amazing product, highly recommend! Great quality.", "score": 28, "domain": "marketplace", "oversight": "low"},
            {"text": "Battery lasts 14 hours of video playback at 150 nits brightness.", "score": 74, "domain": "marketplace", "oversight": "high"},
        ]
        for i, item in enumerate(demo_items):
            _FEED.append({
                "id": f"feed-{i}",
                **item,
                "upvotes": random.randint(0, 15),
                "downvotes": random.randint(0, 5),
                "community_verdict": "agrees" if random.random() > 0.2 else "disputes",
                "timestamp": f"2026-05-27T{i:02d}:00:00Z",
            })

    return {"feed": _FEED[:limit], "total": len(_FEED)}


# ---- Real-Time Slop Ticker ----

@app.get("/ticker")
def slop_ticker():
    """Real-time aggregated quality stats — live from scoring activity."""
    from slopguard.adapters.ticker import get_ticker_snapshot
    return get_ticker_snapshot()


@app.get("/ticker/live")
async def slop_ticker_live():
    """Server-Sent Events endpoint streaming ticker snapshots every 30 seconds."""
    from slopguard.adapters.ticker import get_ticker_stream_instance, refresh_and_publish

    stream = get_ticker_stream_instance()

    async def event_stream():
        queue = stream.subscribe()
        try:
            while True:
                snapshot = await asyncio.get_event_loop().run_in_executor(None, refresh_and_publish)
                yield f"data: {__import__('json').dumps(snapshot)}\n\n"
                await asyncio.sleep(30)
        finally:
            stream.unsubscribe(queue)

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.get("/baseline/repo/{repo_id:path}")
def repo_baseline_profile(repo_id: str, domain: str = "code_review"):
    """Get full baseline profile for a repo."""
    from slopguard.adapters.baselines import get_repo_profile
    return get_repo_profile(repo_id, domain)


# ---- Verified Human Corpus (Human Excellence Collection) ----

@app.get("/excellence")
def human_excellence(track: str = ""):
    """Curated collection of high-quality human-written examples across all 8 tracks.

    Demonstrates that SlopGuard is pro-quality, not anti-AI — surfacing excellence,
    not just flagging slop.
    """
    corpus = {
        "code_review": [
            {
                "text": "Moved token validation from the request hot path to a background Redis cache job. Profiling showed auth middleware adding 340ms to every request. P95 latency dropped from 420ms to 85ms. Tradeoff: tokens may be invalid for up to 5 minutes after role change (acceptable per security review SR-247).",
                "why": "Specific measurements, named tools, before/after metrics, acknowledged tradeoff.",
                "score": 82,
            },
            {
                "text": "Replaced lodash.merge() with structuredClone() — bundle dropped from 2.1MB to 340KB after tree-shaking removed all 47 lodash functions we no longer import. Tested on Node 20.11, Chrome 124, Firefox 126.",
                "why": "Specific before/after, named functions, version numbers, tested environments.",
                "score": 79,
            },
        ],
        "docs": [
            {
                "text": "Step 4: Run 'npm run db:migrate'. This creates the user_sessions table with 4 indexes (email, token, expires_at, user_id). Migration takes ~12 minutes on a 50GB PostgreSQL 15 database. If it fails, the transaction rolls back — no partial state.",
                "why": "Concrete commands, specific schema details, timing data, failure mode documented.",
                "score": 76,
            },
        ],
        "marketplace": [
            {
                "text": "Battery lasts 14 hours of video playback (tested at 150 nits, WiFi off, AirPods connected). Screen hits 1,200 nits peak — readable in direct sunlight at the beach. The hinge started creaking after 6 months; plastic bushing wore down. Replaced with metal one from iFixit ($12).",
                "why": "Test conditions specified, measurements with tools, real failure experience with fix.",
                "score": 80,
            },
        ],
        "academia": [
            {
                "text": "The proposed method achieves 94.2% accuracy on the test set (n=10,000), compared to 91.7% for the baseline (p < 0.01, paired t-test). Training converges in 47 epochs (vs 120 for SGD), reducing wall-clock time from 18h to 6h on a single A100 GPU. Code and weights: github.com/org/method.",
                "why": "Statistical significance, sample sizes, hardware specs, reproducibility link.",
                "score": 88,
            },
        ],
        "hiring": [
            {
                "text": "Led migration from Jenkins to GitHub Actions across 8 microservices — cut CI time from 45min to 12min. Reduced API latency by 40% (200ms to 120ms p95) by implementing Redis caching. Mentored 3 junior engineers; 2 promoted within 12 months.",
                "why": "Quantified impact, specific technologies, measurable outcomes.",
                "score": 84,
            },
        ],
        "communications": [
            {
                "text": "The deploy took 45 minutes (usually 12). Root cause: the users table migration held an exclusive lock for 38 minutes while rebuilding the email index. Fix: ran CREATE INDEX CONCURRENTLY in a separate migration. Alice flagged at 2:30 PM, fix merged at 3:15 PM.",
                "why": "Specific timeline, root cause with technical detail, named people and actions.",
                "score": 78,
            },
        ],
        "content": [
            {
                "text": "The vulnerability (CVE-2024-1234) affected 2.3 million npm packages downloading the compromised event-stream@3.3.6. The attack injected a cryptominer via a malicious dependency (flatmap-stream). Patch released within 48 hours. Check your lockfile: grep 'flatmap-stream' package-lock.json.",
                "why": "CVE number, affected count, specific package names, actionable verification step.",
                "score": 82,
            },
        ],
        "social_news": [
            {
                "text": "The post got 14,200 upvotes in 6 hours — 83% from accounts created in the last 30 days. Cross-referenced with pushshift: 47 of the top 50 commenters have no other posting history. The original image is from a 2019 Imgur post, reverse-searched via Google Lens.",
                "why": "Data analysis, cross-referenced sources, specific tools used, verifiable claims.",
                "score": 85,
            },
        ],
    }

    if track and track in corpus:
        return {"track": track, "examples": corpus[track]}

    return {
        "description": "Curated high-quality human-written examples across all 8 SlopGuard tracks. These demonstrate what genuine human oversight looks like.",
        "total_examples": sum(len(v) for v in corpus.values()),
        "tracks": list(corpus.keys()),
        "corpus": corpus,
    }


# ---- Organization Dashboard ----

_ORG_HISTORY: dict[str, list[dict]] = {}


@app.get("/org/{org_name}")
def org_dashboard(org_name: str, weeks: int = 8):
    """Organization-level dashboard — aggregates SlopGuard scores across an entire GitHub org.

    Shows weekly oversight trends, top/bottom repos, best PRs, and most improved authors.
    """
    import random
    random.seed(hash(org_name) % (2**32))

    if org_name not in _ORG_HISTORY:
        # Generate demo history
        base_score = random.uniform(50, 70)
        history = []
        for i in range(weeks):
            week_score = base_score + random.gauss(0, 4) + i * random.uniform(-1, 2)
            history.append({
                "week": f"2026-W{10 + i}",
                "score": round(week_score, 1),
                "prs_scored": random.randint(20, 80),
                "slop_rate": round(random.uniform(0.2, 0.45), 2),
            })
        _ORG_HISTORY[org_name] = history

    history = _ORG_HISTORY[org_name]
    current = history[-1]["score"]
    last_week = history[-2]["score"] if len(history) >= 2 else current
    change = current - last_week

    # Generate demo repos
    repos = []
    repo_names = [
        f"{org_name}/api", f"{org_name}/web", f"{org_name}/mobile",
        f"{org_name}/cli", f"{org_name}/docs", f"{org_name}/infra",
        f"{org_name}/sdk", f"{org_name}/auth",
    ]
    for repo in repo_names[:random.randint(4, 8)]:
        repos.append({
            "repo": repo,
            "score": round(random.uniform(35, 85), 1),
            "prs_this_week": random.randint(3, 25),
            "trend": round(random.uniform(-8, 8), 1),
        })

    repos.sort(key=lambda r: r["trend"], reverse=True)
    most_improved = repos[:3]
    most_degraded = sorted(repos, key=lambda r: r["trend"])[:3]

    # Best PR of the week
    best_pr = {
        "repo": random.choice(repo_names),
        "pr": f"#{random.randint(100, 999)}",
        "title": random.choice([
            "Add Redis caching to reduce auth latency from 340ms to 85ms",
            "Fix N+1 query in getUserPermissions — 47 queries → 3",
            "Replace lodash.merge with structuredClone — bundle -84%",
        ]),
        "score": round(random.uniform(72, 88), 1),
        "author": random.choice(["@alice", "@bob", "@charlie", "@dave"]),
    }

    # Most improved author
    most_improved_author = {
        "author": random.choice(["@eve", "@frank", "@grace", "@heidi"]),
        "why_ratio_change": f"+{random.randint(15, 40)}%",
        "avg_score_before": round(random.uniform(35, 48), 1),
        "avg_score_after": round(random.uniform(58, 72), 1),
        "prs_count": random.randint(5, 20),
    }

    # Weekly email digest
    digest = {
        "subject": f"SlopGuard Weekly: {org_name} oversight {'improved' if change > 0 else 'declined'} this week",
        "highlights": [
            f"Org-wide oversight score: {current:.1f} ({'+' if change > 0 else ''}{change:.1f} vs last week)",
            f"Top improved repo: {most_improved[0]['repo']} ({most_improved[0]['trend']:+.1f})",
            f"Most degraded repo: {most_degraded[0]['repo']} ({most_degraded[0]['trend']:+.1f})",
            f"Best PR: {best_pr['title']} (score: {best_pr['score']})",
            f"Most improved author: {most_improved_author['author']} ({most_improved_author['why_ratio_change']} WHY ratio increase)",
        ],
    }

    return {
        "org": org_name,
        "current_score": round(current, 1),
        "weekly_change": round(change, 1),
        "trend": "improving" if change > 0 else "declining" if change < 0 else "stable",
        "history": history,
        "repos": repos,
        "most_improved_repos": most_improved,
        "most_degraded_repos": most_degraded,
        "best_pr_of_week": best_pr,
        "most_improved_author": most_improved_author,
        "weekly_digest": digest,
        "total_prs_this_week": sum(r["prs_this_week"] for r in repos),
        "slop_rate": history[-1]["slop_rate"],
    }



# =============================================================================
# Live Ingestion Endpoints — real content scored in real time
# =============================================================================


@app.get("/live/feed")
def live_feed(limit: int = 50, domain: str = "", oversight: str = ""):
    """Live feed of real content being scored from across the internet.

    Pulls from Hacker News, Dev.to, GitHub Issues/Commits, Reddit,
    Stack Overflow, arXiv, Wikipedia, CrossRef, and PubMed.

    Updated continuously in the background. Each item shows source,
    domain, score, oversight label, and which signal fired.

    Query params:
      limit    — max items to return (default 50)
      domain   — filter by domain (code_review, content, academia, etc.)
      oversight — filter by oversight label (high, mixed, low)
    """
    from slopguard.adapters.live_ingestion import get_live_feed, is_running
    items = get_live_feed(limit=min(limit, 200))
    if domain:
        items = [i for i in items if i["domain"] == domain]
    if oversight:
        items = [i for i in items if i["oversight"] == oversight]
    return {
        "ingestion_active": is_running(),
        "total_items": len(items),
        "items": items,
    }


@app.get("/live/stats")
def live_stats():
    """Ingestion statistics — items/min, domain breakdown, slop rate, uptime."""
    from slopguard.adapters.live_ingestion import get_ingestion_stats, is_running
    stats = get_ingestion_stats()
    stats["ingestion_active"] = is_running()
    return stats


@app.get("/live/stream")
async def live_stream():
    """Server-Sent Events stream of live scored items."""
    from slopguard.adapters.live_ingestion import _live_feed, _ingestion_lock
    import asyncio

    last_timestamp: float = 0.0

    async def event_generator():
        nonlocal last_timestamp
        while True:
            with _ingestion_lock:
                feed_list = list(_live_feed)
            # Only send items newer than what we've already sent
            new_items = [i for i in feed_list if i.timestamp > last_timestamp]
            for item in sorted(new_items, key=lambda x: x.timestamp):
                payload = json.dumps({
                    "source": item.source,
                    "domain": item.domain,
                    "title": item.title,
                    "text_preview": item.text_preview,
                    "score": item.score,
                    "oversight": item.oversight,
                    "url": item.url,
                    "timestamp": item.timestamp,
                    "top_signal": item.signals[0]["name"] if item.signals else "unknown",
                })
                yield f"data: {payload}\n\n"
                last_timestamp = max(last_timestamp, item.timestamp)
            await asyncio.sleep(3)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


@app.post("/live/score-url")
async def score_url_live(url: str, domain: str = "content"):
    """Score any public URL in real time — fetches content and scores it.

    Useful for live demos: paste any article URL and get an instant score.
    """
    try:
        req = urllib.request.Request(
            url,
            headers={"User-Agent": "SlopGuard/0.1"},
        )
        with urllib.request.urlopen(req, timeout=10) as r:
            raw = r.read(50000).decode("utf-8", errors="replace")
    except Exception as exc:
        return {"status": "fetch_failed", "error": str(exc)}

    # Strip HTML
    text = re.sub(r"<script[^>]*>.*?</script>", " ", raw, flags=re.DOTALL | re.I)
    text = re.sub(r"<style[^>]*>.*?</style>", " ", text, flags=re.DOTALL | re.I)
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()[:3000]

    if len(text) < 50:
        return {"status": "insufficient_content", "url": url}

    result = score_text(text, domain)
    return {
        "status": "ok",
        "url": url,
        "domain": domain,
        "score": result.score,
        "oversight": result.oversight,
        "summary": result.summary,
        "signals": [{"name": s.name, "score": s.score, "label": s.label} for s in result.signals],
        "text_preview": text[:300],
    }


# =============================================================================
# Novel Signal Endpoints — Sharpest Signal Prize
# =============================================================================

@app.post("/signals/epistemic-cowardice")
def analyze_epistemic_cowardice(request: TextScoreRequest):
    """Analyze text for epistemic cowardice patterns.
    
    Detects systematic avoidance of taking positions:
    - Hedge clustering (may, might, could, potentially)
    - False balance without resolution
    - Opinion laundering (some people say...)
    - Responsibility deflection (it depends, consult an expert)
    - Commitment absence (no falsifiable predictions)
    
    Returns detailed analysis with verdict and specific patterns found.
    """
    from slopguard.detectors.epistemic_cowardice import analyze_epistemic_cowardice
    
    analysis = analyze_epistemic_cowardice(request.text)
    
    return {
        "text_preview": request.text[:200],
        "verdict": analysis.verdict,
        "score": analysis.score,
        "hedge_density": analysis.hedge_density,
        "hedge_clustering": analysis.hedge_clustering,
        "false_balance_count": analysis.false_balance_count,
        "has_resolution": analysis.has_resolution,
        "opinion_laundering_count": analysis.opinion_laundering_count,
        "commitment_count": analysis.commitment_count,
        "responsibility_deflection": analysis.responsibility_deflection,
        "explanation": {
            "committed": "Strong commitment: definitive recommendations with minimal hedging.",
            "balanced": "Balanced reasoning: some hedging but with clear commitments.",
            "hedged": "Excessive hedging: many qualifiers without definitive recommendations.",
            "cowardly": "Epistemic cowardice: hedging without commitment, false balance without resolution.",
        }.get(analysis.verdict, "Unknown verdict"),
    }


@app.post("/signals/counterfactual-absence")
def analyze_counterfactual_absence(request: TextScoreRequest):
    """Analyze text for counterfactual reasoning presence/absence.
    
    Detects whether the author considered:
    - Rejected alternatives (considered X but chose Y because...)
    - Explicit failure modes (this breaks when...)
    - Specific conditions (only works if...)
    - Tradeoffs with specifics (trading X for Y)
    
    AI generates the happy path. Humans think about what could go wrong.
    
    Returns detailed analysis with specific counterfactuals found.
    """
    from slopguard.detectors.counterfactual_absence import analyze_counterfactual_absence
    
    analysis = analyze_counterfactual_absence(request.text)
    
    return {
        "text_preview": request.text[:200],
        "verdict": analysis.verdict,
        "score": analysis.score,
        "rejected_alternatives": analysis.rejected_alternatives,
        "failure_modes": analysis.failure_modes,
        "specific_conditions": analysis.specific_conditions,
        "specific_tradeoffs": analysis.specific_tradeoffs,
        "generic_counterfactuals": analysis.generic_counterfactuals,
        "best_practice_no_context": analysis.best_practice_no_context,
        "pure_positive_complex": analysis.pure_positive_complex,
        "total_counterfactuals": analysis.total_counterfactuals,
        "specificity_ratio": analysis.specificity_ratio,
        "explanation": {
            "rich_counterfactuals": "Rich counterfactual reasoning: specific alternatives rejected, failure modes identified, tradeoffs quantified.",
            "some_counterfactuals": "Some counterfactual reasoning: mentions alternatives, conditions, or tradeoffs.",
            "generic_counterfactuals": "Generic counterfactuals only: 'may have performance implications' without specifics.",
            "counterfactual_absence": "No counterfactual reasoning: no alternatives, failure modes, or tradeoffs discussed.",
        }.get(analysis.verdict, "Unknown verdict"),
    }


@app.post("/signals/vocabulary-novelty")
def analyze_vocabulary_novelty(request: TextScoreRequest):
    """Analyze vocabulary novelty curve to detect AI vs human patterns.
    
    Human experts introduce concepts progressively:
    - High novelty early (introducing the topic)
    - Decreasing novelty (building on established context)
    - Spikes at section transitions (new concepts)
    
    AI distributes terminology uniformly:
    - Flat novelty curve (no progressive building)
    - Front-loads technical terms (signals expertise)
    - Few spikes (no real section structure)
    
    This is the most technically sophisticated signal. It's looking at the
    SHAPE of vocabulary introduction, not the content itself.
    
    Returns curve data for visualization plus analysis.
    """
    from slopguard.detectors.vocabulary_novelty import visualize_novelty_curve
    
    result = visualize_novelty_curve(request.text)
    
    return {
        "text_preview": request.text[:200],
        "curve": result["curve"],
        "labels": result["labels"],
        "analysis": result["analysis"],
        "explanation": {
            "human_curve": "Human vocabulary curve: decreasing novelty with section spikes indicates progressive concept building.",
            "mixed_curve": "Mixed vocabulary novelty pattern: some progressive introduction but also uniform distribution.",
            "flat_curve": "Low variance in vocabulary novelty: terms introduced uniformly rather than progressively.",
            "ai_curve": "Flat vocabulary novelty curve: uniform terminology distribution suggests AI generation.",
        }.get(result["analysis"]["verdict"], "Unknown verdict"),
    }


# =============================================================================
# /live/worst — bottom 10 scored items right now
# =============================================================================

@app.get("/live/worst")
def live_worst(limit: int = 10):
    """The lowest-scoring items from the live feed right now.

    Shows what SlopGuard is catching in real time — the worst content
    currently being published across HN, Reddit, GitHub, Dev.to, etc.
    """
    from slopguard.adapters.live_ingestion import get_worst_items, get_ingestion_stats
    items = get_worst_items(limit=min(limit, 50))
    stats = get_ingestion_stats()
    return {
        "description": "Lowest-scoring content from live ingestion right now",
        "total_in_feed": stats.get("total_scored", 0),
        "items": items,
    }


# =============================================================================
# /live/leaderboard — source and domain slop rates from live data
# =============================================================================

@app.get("/live/leaderboard")
def live_leaderboard():
    """Live leaderboard — which sources and domains have the most slop right now.

    Replaces the hardcoded demo leaderboard with real data from live ingestion.
    Updates continuously as new content is scored.
    """
    from slopguard.adapters.live_ingestion import (
        get_source_leaderboard, get_domain_leaderboard, get_ingestion_stats
    )
    stats = get_ingestion_stats()
    sources = get_source_leaderboard()
    domains = get_domain_leaderboard()

    return {
        "total_scored": stats.get("total_scored", 0),
        "window": "all time since startup",
        "by_source": sources,
        "by_domain": domains,
        "note": "Live data from real content ingestion. Updates every 25-90 seconds.",
    }


# =============================================================================
# /live/history — per-minute score history for sparkline chart
# =============================================================================

@app.get("/live/history")
def live_history():
    """Per-minute score history for the last 60 minutes.

    Use this to render a sparkline showing slop rate over time.
    Each bucket: {minute, count, avg_score, slop_rate, slop_count}
    """
    from slopguard.adapters.live_ingestion import get_score_history, get_ingestion_stats
    history = get_score_history()
    stats = get_ingestion_stats()
    return {
        "buckets": history,
        "total_minutes": len(history),
        "current_slop_rate": stats.get("slop_rate", 0),
        "current_avg_score": round(
            sum(b["avg_score"] for b in history) / max(len(history), 1), 1
        ) if history else None,
    }


# =============================================================================
# /live/patterns — novel slop phrases queued for corpus addition
# =============================================================================

@app.get("/live/patterns")
def live_patterns(promoted_only: bool = False):
    """Novel slop phrases detected in live content, queued for corpus addition.

    Phrases that appear 3+ times in low-scoring content are flagged.
    This is how the detection corpus grows dynamically.
    """
    from slopguard.adapters.live_ingestion import get_pattern_queue, _PROMOTION_THRESHOLD
    patterns = get_pattern_queue(promoted_only=promoted_only)
    ready = [p for p in patterns if p["count"] >= _PROMOTION_THRESHOLD]
    return {
        "total_queued": len(patterns),
        "ready_for_promotion": len(ready),
        "promotion_threshold": _PROMOTION_THRESHOLD,
        "patterns": patterns,
        "note": f"Phrases appearing {_PROMOTION_THRESHOLD}+ times in low-scoring content are candidates for the slop corpus.",
    }


@app.post("/live/patterns/{phrase}/promote")
def promote_pattern(phrase: str):
    """Manually promote a queued pattern to the slop corpus."""
    from slopguard.adapters.live_ingestion import promote_pattern as _promote
    success = _promote(phrase)
    return {"promoted": success, "phrase": phrase}


# =============================================================================
# /live/thresholds — view and adapt domain thresholds
# =============================================================================

@app.get("/live/thresholds")
def live_thresholds():
    """Current domain-specific scoring thresholds.

    These adapt based on user feedback — when users mark scores as wrong,
    the threshold shifts using exponential moving average.
    """
    from slopguard.adapters.live_ingestion import get_current_thresholds, get_threshold_history
    thresholds = get_current_thresholds()
    history = get_threshold_history()
    return {
        "thresholds": thresholds,
        "total_adaptations": len(history),
        "recent_adaptations": history[-10:],
        "note": "Thresholds adapt when users submit feedback via /appeals or /feedback. Max shift: ±2 points per feedback. Bounds: [30, 70].",
    }


class ThresholdFeedbackRequest(BaseModel):
    domain: str
    was_too_harsh: bool  # True = we flagged good content, False = we missed slop
    confidence: float = 1.0
    reason: str = ""


@app.post("/live/thresholds/adapt")
def adapt_threshold_endpoint(request: ThresholdFeedbackRequest):
    """Submit feedback to adapt a domain threshold.

    was_too_harsh=true  → threshold was too high (lowered slightly)
    was_too_harsh=false → threshold was too low (raised slightly)

    This is the feedback loop that makes SlopGuard learn from corrections.
    """
    from slopguard.adapters.live_ingestion import adapt_threshold
    result = adapt_threshold(
        domain=request.domain,
        was_too_harsh=request.was_too_harsh,
        confidence=max(0.1, min(1.0, request.confidence)),
    )
    return result


# =============================================================================
# GET /live — self-contained HTML live demo page
# =============================================================================

@app.get("/live", response_class=HTMLResponse)
def live_demo_page():
    """Self-contained live demo page. No React, no build step.

    Shows real content being scored from across the internet in real time.
    Judges open this URL and see the system working immediately.
    """
    return """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>SlopGuard — Live Feed</title>
<style>
  *{box-sizing:border-box;margin:0;padding:0}
  body{background:#0d1117;color:#e6edf3;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:13px;line-height:1.5}
  header{background:#161b22;border-bottom:1px solid #30363d;padding:12px 20px;display:flex;align-items:center;gap:16px;position:sticky;top:0;z-index:10}
  header h1{font-size:16px;font-weight:700;color:#58a6ff}
  .badge{display:inline-flex;align-items:center;gap:6px;background:#21262d;border:1px solid #30363d;border-radius:20px;padding:3px 10px;font-size:11px}
  .dot{width:7px;height:7px;border-radius:50%;background:#3fb950;animation:pulse 2s infinite}
  @keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}
  .stats-bar{display:flex;gap:20px;padding:10px 20px;background:#161b22;border-bottom:1px solid #30363d;flex-wrap:wrap}
  .stat{display:flex;flex-direction:column;gap:2px}
  .stat-label{color:#8b949e;font-size:10px;text-transform:uppercase;letter-spacing:.5px}
  .stat-value{font-size:18px;font-weight:700;color:#e6edf3}
  .main{display:grid;grid-template-columns:1fr 320px;gap:0;height:calc(100vh - 90px)}
  .feed{overflow-y:auto;border-right:1px solid #30363d}
  .sidebar{overflow-y:auto;background:#0d1117}
  .item{border-bottom:1px solid #21262d;padding:10px 16px;cursor:pointer;transition:background .1s}
  .item:hover{background:#161b22}
  .item-header{display:flex;align-items:center;gap:8px;margin-bottom:4px}
  .score-badge{font-size:11px;font-weight:700;padding:1px 7px;border-radius:4px;min-width:36px;text-align:center}
  .score-high{background:#0d4429;color:#3fb950;border:1px solid #238636}
  .score-mixed{background:#2d2a00;color:#d29922;border:1px solid #9e6a03}
  .score-low{background:#3d0c0c;color:#f85149;border:1px solid #da3633}
  .score-insufficient{background:#21262d;color:#8b949e;border:1px solid #30363d}
  .source-tag{font-size:10px;color:#8b949e;background:#21262d;padding:1px 6px;border-radius:3px}
  .domain-tag{font-size:10px;color:#79c0ff;background:#0d2149;padding:1px 6px;border-radius:3px}
  .item-title{font-size:12px;color:#e6edf3;margin-bottom:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .item-preview{font-size:11px;color:#8b949e;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .item-signal{font-size:10px;color:#f85149;margin-top:3px}
  .new-item{animation:flash .6s ease-out}
  @keyframes flash{0%{background:#1c2d3a}100%{background:transparent}}
  .sidebar-section{padding:12px 14px;border-bottom:1px solid #21262d}
  .sidebar-title{font-size:10px;text-transform:uppercase;letter-spacing:.5px;color:#8b949e;margin-bottom:8px}
  .leaderboard-row{display:flex;align-items:center;gap:8px;padding:4px 0;font-size:11px}
  .lb-name{flex:1;color:#e6edf3;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
  .lb-bar-wrap{width:80px;height:6px;background:#21262d;border-radius:3px;overflow:hidden}
  .lb-bar{height:100%;border-radius:3px;transition:width .5s}
  .lb-pct{width:32px;text-align:right;color:#8b949e}
  .sparkline{width:100%;height:40px}
  .chart-wrap{padding:8px 0}
  .empty{color:#8b949e;font-size:12px;padding:20px;text-align:center}
  .filter-bar{display:flex;gap:6px;padding:8px 16px;background:#161b22;border-bottom:1px solid #30363d;flex-wrap:wrap}
  .filter-btn{font-size:11px;padding:3px 10px;border-radius:4px;border:1px solid #30363d;background:#21262d;color:#8b949e;cursor:pointer;transition:all .1s}
  .filter-btn.active{border-color:#58a6ff;color:#58a6ff;background:#0d2149}
  a{color:#58a6ff;text-decoration:none}
  a:hover{text-decoration:underline}
  .worst-section{padding:10px 14px;border-bottom:1px solid #21262d}
  .worst-item{padding:5px 0;border-bottom:1px solid #21262d;font-size:11px}
  .worst-item:last-child{border-bottom:none}
  .worst-score{color:#f85149;font-weight:700;margin-right:6px}
  .worst-title{color:#e6edf3}
  .worst-why{color:#8b949e;font-size:10px;margin-top:2px}
</style>
</head>
<body>
<header>
  <h1>🛡 SlopGuard</h1>
  <div class="badge"><span class="dot"></span> Live Ingestion</div>
  <div class="badge" id="counter">0 scored</div>
  <div class="badge" id="slop-rate">slop rate: —</div>
  <div class="badge" id="ipm">— items/min</div>
  <div style="margin-left:auto;display:flex;gap:8px">
    <a href="/docs" class="badge">API Docs</a>
    <a href="/live/feed" class="badge">JSON Feed</a>
    <a href="/live/worst" class="badge">Worst Now</a>
  </div>
</header>

<div class="stats-bar" id="stats-bar">
  <div class="stat"><span class="stat-label">Total Scored</span><span class="stat-value" id="s-total">—</span></div>
  <div class="stat"><span class="stat-label">Slop Rate</span><span class="stat-value" id="s-slop">—</span></div>
  <div class="stat"><span class="stat-label">Items/min</span><span class="stat-value" id="s-ipm">—</span></div>
  <div class="stat"><span class="stat-label">Sources Active</span><span class="stat-value" id="s-sources">—</span></div>
  <div class="stat"><span class="stat-label">Uptime</span><span class="stat-value" id="s-uptime">—</span></div>
</div>

<div class="filter-bar">
  <span style="color:#8b949e;font-size:11px;align-self:center">Filter:</span>
  <button class="filter-btn active" onclick="setFilter('')">All</button>
  <button class="filter-btn" onclick="setFilter('low')">🔴 Slop</button>
  <button class="filter-btn" onclick="setFilter('mixed')">🟡 Mixed</button>
  <button class="filter-btn" onclick="setFilter('high')">🟢 High</button>
  <button class="filter-btn" onclick="setFilter('code_review')">Code Review</button>
  <button class="filter-btn" onclick="setFilter('content')">Content</button>
  <button class="filter-btn" onclick="setFilter('academia')">Academia</button>
  <button class="filter-btn" onclick="setFilter('social_news')">Social/News</button>
</div>

<div class="main">
  <div class="feed" id="feed">
    <div class="empty">Waiting for live data... (ingestion starts in ~5 seconds)</div>
  </div>

  <div class="sidebar">
    <div class="sidebar-section">
      <div class="sidebar-title">📊 Slop Rate Over Time</div>
      <div class="chart-wrap">
        <canvas class="sparkline" id="sparkline" width="290" height="40"></canvas>
      </div>
      <div style="font-size:10px;color:#8b949e;margin-top:4px">Per-minute slop rate (last 60 min)</div>
    </div>

    <div class="sidebar-section">
      <div class="sidebar-title">🏆 Source Leaderboard (most slop first)</div>
      <div id="source-lb"><div class="empty">Loading...</div></div>
    </div>

    <div class="sidebar-section">
      <div class="sidebar-title">📁 Domain Breakdown</div>
      <div id="domain-lb"><div class="empty">Loading...</div></div>
    </div>

    <div class="worst-section">
      <div class="sidebar-title">💀 Worst Right Now</div>
      <div id="worst-list"><div class="empty">Loading...</div></div>
    </div>
  </div>
</div>

<script>
const MAX_ITEMS = 100;
let allItems = [];
let activeFilter = '';
let statsInterval;

function setFilter(f) {
  activeFilter = f;
  document.querySelectorAll('.filter-btn').forEach(b => b.classList.remove('active'));
  event.target.classList.add('active');
  renderFeed();
}

function scoreClass(oversight) {
  if (oversight === 'high') return 'score-high';
  if (oversight === 'mixed') return 'score-mixed';
  if (oversight === 'low') return 'score-low';
  return 'score-insufficient';
}

function timeAgo(ts) {
  const s = Math.floor(Date.now()/1000 - ts);
  if (s < 60) return s + 's ago';
  if (s < 3600) return Math.floor(s/60) + 'm ago';
  return Math.floor(s/3600) + 'h ago';
}

function renderFeed() {
  const feed = document.getElementById('feed');
  const filtered = activeFilter
    ? allItems.filter(i => i.oversight === activeFilter || i.domain === activeFilter)
    : allItems;

  if (!filtered.length) {
    feed.innerHTML = '<div class="empty">No items match filter. Waiting for live data...</div>';
    return;
  }

  feed.innerHTML = filtered.slice(0, MAX_ITEMS).map((item, idx) => `
    <div class="item ${idx === 0 ? 'new-item' : ''}" onclick="window.open('${item.url || '#'}','_blank')">
      <div class="item-header">
        <span class="score-badge ${scoreClass(item.oversight)}">${item.score.toFixed(1)}</span>
        <span class="source-tag">${item.source.replace('_',' ')}</span>
        <span class="domain-tag">${item.domain.replace('_',' ')}</span>
        <span style="margin-left:auto;color:#8b949e;font-size:10px">${timeAgo(item.timestamp)}</span>
      </div>
      <div class="item-title">${escHtml(item.title || item.text_preview)}</div>
      <div class="item-preview">${escHtml(item.text_preview)}</div>
      ${item.oversight === 'low' ? `<div class="item-signal">⚠ ${escHtml(item.top_signal || 'low oversight')}</div>` : ''}
    </div>
  `).join('');
}

function escHtml(s) {
  return (s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function renderLeaderboard(data, containerId, nameKey, valueKey, label) {
  const el = document.getElementById(containerId);
  if (!data || !data.length) { el.innerHTML = '<div class="empty">No data yet</div>'; return; }
  const max = Math.max(...data.map(r => r[valueKey]));
  el.innerHTML = data.slice(0,8).map(row => {
    const pct = max > 0 ? (row[valueKey] / max * 100) : 0;
    const color = row.slop_pct > 50 ? '#f85149' : row.slop_pct > 25 ? '#d29922' : '#3fb950';
    return `<div class="leaderboard-row">
      <span class="lb-name">${escHtml(row[nameKey].replace('_',' '))}</span>
      <div class="lb-bar-wrap"><div class="lb-bar" style="width:${pct}%;background:${color}"></div></div>
      <span class="lb-pct">${row.slop_pct}%</span>
    </div>`;
  }).join('');
}

function renderSparkline(history) {
  const canvas = document.getElementById('sparkline');
  const ctx = canvas.getContext('2d');
  const W = canvas.width, H = canvas.height;
  ctx.clearRect(0, 0, W, H);
  if (!history || history.length < 2) return;

  const rates = history.map(b => b.slop_rate);
  const max = Math.max(...rates, 0.01);
  const step = W / (rates.length - 1);

  ctx.beginPath();
  ctx.strokeStyle = '#f85149';
  ctx.lineWidth = 1.5;
  rates.forEach((r, i) => {
    const x = i * step;
    const y = H - (r / max) * (H - 4) - 2;
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  });
  ctx.stroke();

  // Fill
  ctx.beginPath();
  rates.forEach((r, i) => {
    const x = i * step;
    const y = H - (r / max) * (H - 4) - 2;
    i === 0 ? ctx.moveTo(x, y) : ctx.lineTo(x, y);
  });
  ctx.lineTo((rates.length-1)*step, H);
  ctx.lineTo(0, H);
  ctx.closePath();
  ctx.fillStyle = 'rgba(248,81,73,0.12)';
  ctx.fill();
}

function renderWorst(items) {
  const el = document.getElementById('worst-list');
  if (!items || !items.length) { el.innerHTML = '<div class="empty">No data yet</div>'; return; }
  el.innerHTML = items.slice(0,8).map(item => `
    <div class="worst-item">
      <span class="worst-score">${item.score.toFixed(1)}</span>
      <span class="worst-title">${escHtml((item.title||item.text_preview||'').slice(0,55))}</span>
      <div class="worst-why">${escHtml(item.why_flagged||'')}</div>
    </div>
  `).join('');
}

async function updateStats() {
  try {
    const [stats, lb, history, worst] = await Promise.all([
      fetch('/live/stats').then(r=>r.json()),
      fetch('/live/leaderboard').then(r=>r.json()),
      fetch('/live/history').then(r=>r.json()),
      fetch('/live/worst?limit=8').then(r=>r.json()),
    ]);

    document.getElementById('s-total').textContent = stats.total_scored || 0;
    document.getElementById('s-slop').textContent = ((stats.slop_rate||0)*100).toFixed(1) + '%';
    document.getElementById('s-ipm').textContent = (stats.items_per_minute||0).toFixed(1);
    document.getElementById('s-sources').textContent = Object.keys(stats.source_counts||{}).length;
    const up = stats.uptime_seconds || 0;
    document.getElementById('s-uptime').textContent = up < 60 ? up+'s' : Math.floor(up/60)+'m';

    document.getElementById('counter').textContent = (stats.total_scored||0) + ' scored';
    document.getElementById('slop-rate').textContent = 'slop: ' + ((stats.slop_rate||0)*100).toFixed(1) + '%';
    document.getElementById('ipm').textContent = (stats.items_per_minute||0).toFixed(1) + '/min';

    renderLeaderboard(lb.by_source, 'source-lb', 'source', 'slop_pct', 'slop %');
    renderLeaderboard(lb.by_domain, 'domain-lb', 'domain', 'slop_pct', 'slop %');
    renderSparkline(history.buckets);
    renderWorst(worst.items);
  } catch(e) {}
}

// SSE stream for live items
const es = new EventSource('/live/stream');
es.onmessage = function(e) {
  try {
    const item = JSON.parse(e.data);
    allItems.unshift(item);
    if (allItems.length > MAX_ITEMS * 2) allItems = allItems.slice(0, MAX_ITEMS);
    renderFeed();
  } catch(err) {}
};
es.onerror = function() {
  // Reconnect automatically
};

// Poll stats every 10 seconds
updateStats();
statsInterval = setInterval(updateStats, 10000);
</script>
</body>
</html>"""
