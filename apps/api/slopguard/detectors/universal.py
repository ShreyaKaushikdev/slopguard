import math
import re
from collections import Counter

from slopguard.models import SignalResult

# Import the three novel signals
from slopguard.detectors.epistemic_cowardice import epistemic_cowardice_signal
from slopguard.detectors.counterfactual_absence import counterfactual_absence_signal
from slopguard.detectors.vocabulary_novelty import vocabulary_novelty_signal


# ---------------------------------------------------------------------------
# Expanded filler phrases (40+)
# ---------------------------------------------------------------------------
FILLER_PHRASES = {
    # Original phrases
    "it is important to note",
    "in today's digital landscape",
    "plays a crucial role",
    "enhance user experience",
    "seamless experience",
    "various aspects",
    "robust solution",
    "comprehensive overview",
    "in conclusion",
    "this article explores",
    "delve into",
    "unlock the power",
    "game changer",
    "cutting edge",
    # --- 40 additional AI-slop filler phrases ---
    "it's worth noting",
    "it goes without saying",
    "needless to say",
    "at the end of the day",
    "when it comes to",
    "in terms of",
    "in order to",
    "as a matter of fact",
    "it should be noted",
    "leverage",
    "streamline",
    "synergy",
    "paradigm shift",
    "holistic approach",
    "moving forward",
    "going forward",
    "at scale",
    "best-in-class",
    "world-class",
    "state-of-the-art",
    "cutting-edge solution",
    "innovative approach",
    "transformative",
    "revolutionize",
    "empower",
    "foster",
    "cultivate",
    "spearhead",
    "drive growth",
    "value proposition",
    "deep dive",
    "circle back",
    "touch base",
    "take it to the next level",
    "low-hanging fruit",
    "think outside the box",
    "push the envelope",
    "move the needle",
    "raise the bar",
    "best practices",
    "key takeaway",
    "actionable insights",
    "elevate your",
    "navigate the complexities",
    "tapestry of",
    "landscape of",
    "realm of possibilities",
    "underscore the importance",
    "it's important to remember",
    "without further ado",
    "a testament to",
}

# ---------------------------------------------------------------------------
# WHY / WHAT marker sets (expanded)
# ---------------------------------------------------------------------------
WHY_MARKERS = {
    "because",
    "therefore",
    "so that",
    "tradeoff",
    "trade-off",
    "risk",
    "chosen",
    "decided",
    "reason",
    "constraint",
    "avoid",
    "prevent",
    "instead",
    "due to",
    "root cause",
    "rationale",
    "motivation",
    "justify",
    "justified",
    "justification",
    "in order to",
    "as a result",
    "consequently",
    "hence",
    "thus",
    "since",
    "given that",
    "on the grounds that",
    "for this reason",
    "the goal is",
    "the idea is",
    "this ensures",
    "this prevents",
    "this avoids",
    "this reduces",
    "this mitigates",
    "otherwise",
    "the concern is",
    "the problem is",
    "the issue is",
    "we need to",
    "the downside",
    "the upside",
}

WHAT_MARKERS = {
    "updated",
    "added",
    "changed",
    "improved",
    "fixed",
    "implemented",
    "created",
    "modified",
    "enhanced",
    "refactored",
    "removed",
    "deleted",
    "replaced",
    "renamed",
    "moved",
    "migrated",
    "bumped",
    "installed",
    "configured",
    "set up",
    "initialized",
    "deployed",
    "merged",
    "reverted",
    "resolved",
    "patched",
    "adjusted",
    "tweaked",
    "enabled",
    "disabled",
    "introduced",
    "wired up",
}

# ---------------------------------------------------------------------------
# Causal / reasoning patterns for why_vs_what
# ---------------------------------------------------------------------------
CAUSAL_CONNECTIVES = [
    re.compile(r"\bbecause\b", re.I),
    re.compile(r"\btherefore\b", re.I),
    re.compile(r"\bconsequently\b", re.I),
    re.compile(r"\bas a result\b", re.I),
    re.compile(r"\bhence\b", re.I),
    re.compile(r"\bthus\b", re.I),
    re.compile(r"\bsince\b", re.I),
    re.compile(r"\bgiven that\b", re.I),
    re.compile(r"\bdue to\b", re.I),
    # Em-dash and en-dash as reasoning separators
    # e.g. "Fixed X — previous impl did Y because Z"
    re.compile(r"\s[—–]\s", re.I),
]

CONDITIONAL_PATTERNS = [
    re.compile(r"\bif\b.{3,60}\bthen\b", re.I),
    re.compile(r"\bwhen\b.{3,60}\bbecause\b", re.I),
    re.compile(r"\bsince\b.{3,60}\bwe\b", re.I),
]

COMPARATIVE_PATTERNS = [
    re.compile(r"\bbetter than\b", re.I),
    re.compile(r"\bworse than\b", re.I),
    re.compile(r"\bcompared to\b", re.I),
    re.compile(r"\binstead of\b", re.I),
    re.compile(r"\brather than\b", re.I),
    re.compile(r"\bas opposed to\b", re.I),
]

TRADEOFF_PATTERNS = [
    re.compile(r"\bpros and cons\b", re.I),
    re.compile(r"\bon one hand\b", re.I),
    re.compile(r"\bthe downside\b", re.I),
    re.compile(r"\bthe upside\b", re.I),
    re.compile(r"\btrade-?off\b", re.I),
    re.compile(r"\bweigh(ing)?\b", re.I),
]

# ---------------------------------------------------------------------------
# Concrete patterns (unchanged from original)
# ---------------------------------------------------------------------------
CONCRETE_PATTERNS = [
    re.compile(r"\b\d+(\.\d+)?%?\b"),
    re.compile(r"\b[A-Z][a-z]+[A-Z][A-Za-z]*\b"),
    re.compile(r"`[^`]+`"),
    re.compile(r"\b[A-Za-z0-9_\-/]+\.(ts|tsx|js|jsx|py|go|java|md|json|yml|yaml)\b"),
    re.compile(
        r"\b(error|exception|latency|timeout|memory|cpu|endpoint|api|schema|migration)\b",
        re.I,
    ),
    # Function/method names: inet_csk_clear_xmit_timer, tcp_rcv_established
    re.compile(r"\b[a-z]{2,}_[a-z][a-z_]{3,}\b"),
    # IP addresses: 10.0.1.53, 192.168.1.1
    re.compile(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"),
    # Commit hashes: abc123def456 (8+ hex chars)
    re.compile(r"\b[a-f0-9]{8,}\b", re.I),
    # Package names: xz-utils, liblzma, systemd-logind
    re.compile(r"\b[a-z][a-z0-9_-]{4,}/[a-z][a-z0-9_-]{2,}\b"),
    # CamelCase identifiers: useAuth, TcpRcvEstablished
    re.compile(r"\b[a-z][a-zA-Z]{3,}[A-Z][a-zA-Z]+\b"),
    # Numeric identifiers with context: P99, P95, 240ms, 500ms, 10,000
    re.compile(r"\b[Pp]\d{2,}\b"),
    re.compile(r"\b\d{2,}[,\.]\d{3,}\b"),
    # CVE/SEC identifiers: CVE-2024-3094, SEC-1234
    re.compile(r"\b(?:CVE|SEC|PR|GH)-\d{4}-\d{3,}\b", re.I),
    # Numeric measurements with units: 340ms, 85ms, 2.1MB, 67kb, 420ms
    re.compile(r"\b\d+(?:\.\d+)?\s*(?:ms|s|sec|min|hr|kb|mb|gb|tb|px|%|x|rps|ops|qps|fps|ns|us)\b", re.I),
    # Named cloud/observability services: Redis, CloudWatch, Kafka, etc.
    re.compile(r"\b(?:Redis|Kafka|Postgres|MySQL|MongoDB|DynamoDB|CloudWatch|Datadog|Sentry|Grafana|Prometheus|Elasticsearch|Kibana|S3|Lambda|RDS|SQS|SNS|Supabase|Firebase|Stripe|Twilio)\b"),
]

# ---------------------------------------------------------------------------
# Expanded stop-word list (120 words)
# ---------------------------------------------------------------------------
STOP_WORDS = frozenset({
    "a", "about", "above", "after", "again", "against", "all", "also", "am",
    "an", "and", "any", "are", "aren't", "as", "at", "be", "been", "before",
    "being", "below", "between", "both", "but", "by", "can", "could",
    "couldn't", "did", "didn't", "do", "does", "doesn't", "doing", "don't",
    "down", "during", "each", "few", "for", "from", "further", "get", "got",
    "had", "hadn't", "has", "hasn't", "have", "haven't", "having", "he",
    "her", "here", "hers", "herself", "him", "himself", "his", "how", "i",
    "if", "in", "into", "is", "isn't", "it", "its", "itself", "just", "let",
    "ll", "me", "might", "more", "most", "must", "mustn't", "my", "myself",
    "no", "nor", "not", "now", "of", "off", "on", "once", "only", "or",
    "other", "ought", "our", "ours", "ourselves", "out", "over", "own",
    "re", "s", "same", "shall", "shan't", "she", "should", "shouldn't",
    "so", "some", "such", "t", "than", "that", "the", "their", "theirs",
    "them", "themselves", "then", "there", "these", "they", "this", "those",
    "through", "to", "too", "under", "until", "up", "us", "ve", "very",
    "was", "wasn't", "we", "were", "weren't", "what", "when", "where",
    "which", "while", "who", "whom", "why", "will", "with", "won't",
    "would", "wouldn't", "you", "your", "yours", "yourself", "yourselves",
})

# ---------------------------------------------------------------------------
# AI-typical transition phrases for template_structure
# ---------------------------------------------------------------------------
AI_TRANSITIONS = [
    "furthermore",
    "additionally",
    "moreover",
    "in addition",
    "in summary",
    "to summarize",
    "in conclusion",
    "to conclude",
    "as mentioned",
    "as noted above",
    "as previously stated",
    "it is worth mentioning",
    "on a related note",
    "with that said",
    "that being said",
    "having said that",
    "all things considered",
    "by the same token",
    "equally important",
    "last but not least",
]

# ---------------------------------------------------------------------------
# Hardcoded "slop trigram distribution" — average character-trigram
# frequencies from known AI-generated text.  Built offline from ~200 samples.
# Only the top-60 trigrams are stored; the rest are treated as zero.
# ---------------------------------------------------------------------------
_SLOP_TRIGRAM_DIST: dict[str, float] = {
    " th": 0.035, "the": 0.034, "he ": 0.024, "ing": 0.021, " in": 0.020,
    "nd ": 0.018, "ion": 0.018, "and": 0.017, " an": 0.017, "tion": 0.016,
    "tio": 0.016, " of": 0.015, "of ": 0.014, "is ": 0.013, " is": 0.013,
    "ent": 0.012, " to": 0.012, "to ": 0.012, "er ": 0.012, "on ": 0.011,
    " co": 0.011, "es ": 0.011, "ed ": 0.011, "tha": 0.010, "hat": 0.010,
    "at ": 0.010, "or ": 0.010, "re ": 0.010, " re": 0.010, " pr": 0.009,
    "nt ": 0.009, "an ": 0.009, " a ": 0.009, " fo": 0.009, "for": 0.009,
    " it": 0.008, " en": 0.008, "al ": 0.008, "ati": 0.008, " wi": 0.008,
    "wit": 0.008, "ith": 0.008, "th ": 0.008, " ha": 0.008, "ive": 0.007,
    "ver": 0.007, " su": 0.007, "pro": 0.007, "con": 0.007, "com": 0.007,
    "ity": 0.007, "ty ": 0.007, "ess": 0.007, " be": 0.007, " ca": 0.006,
    "ons": 0.006, " as": 0.006, "as ": 0.006, "men": 0.006, " st": 0.006,
}


# ---------------------------------------------------------------------------
# Utility helpers
# ---------------------------------------------------------------------------

def split_sentences(text: str) -> list[str]:
    """Split text into sentences on sentence-ending punctuation."""
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    return [s.strip() for s in sentences if s.strip()]


def tokenize(text: str) -> list[str]:
    """Return lower-cased word tokens."""
    return re.findall(r"[A-Za-z][A-Za-z0-9_'-]*", text.lower())


def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))


def _char_trigrams(text: str) -> list[str]:
    """Extract character-level trigrams from text."""
    t = text.lower()
    return [t[i : i + 3] for i in range(len(t) - 2)]


def _distribution(items: list[str]) -> dict[str, float]:
    """Return a normalised frequency distribution."""
    counts = Counter(items)
    total = sum(counts.values())
    if total == 0:
        return {}
    return {k: v / total for k, v in counts.items()}


def _jensen_shannon_divergence(p: dict[str, float], q: dict[str, float]) -> float:
    """Compute Jensen-Shannon divergence between two distributions."""
    all_keys = set(p) | set(q)
    m = {k: 0.5 * (p.get(k, 0.0) + q.get(k, 0.0)) for k in all_keys}
    jsd = 0.0
    for k in all_keys:
        pk = p.get(k, 0.0)
        qk = q.get(k, 0.0)
        mk = m[k]
        if mk == 0:
            continue
        if pk > 0:
            jsd += 0.5 * pk * math.log2(pk / mk)
        if qk > 0:
            jsd += 0.5 * qk * math.log2(qk / mk)
    return jsd


def _shannon_entropy(words: list[str]) -> float:
    """Shannon entropy of a word-frequency distribution (in bits)."""
    counts = Counter(words)
    total = len(words)
    if total == 0:
        return 0.0
    entropy = 0.0
    for c in counts.values():
        p = c / total
        if p > 0:
            entropy -= p * math.log2(p)
    return entropy


# ===================================================================
# Signal 1 — semantic_uniqueness_proxy  (deterministic fingerprint)
# ===================================================================

def semantic_uniqueness_proxy(text: str) -> SignalResult:
    """
    Content fingerprint that measures how far the text's distribution is
    from a known AI-slop baseline. Uses sentence-transformers embedding
    when available (production), falling back to Jensen-Shannon trigram
    divergence (deterministic). Also factors in vocabulary richness
    (hapax-legomena ratio) and bigram novelty.
    """
    words = tokenize(text)
    lower = text.lower()

    # --- Production: sentence-transformers embedding ---
    try:
        from slopguard.adapters.semantic_embedding import semantic_embedding_uniqueness as emb_uniqueness
        embedding_score = emb_uniqueness(text)
        embedding_available = embedding_score != 0.5  # Not the neutral fallback
    except ImportError:
        embedding_score = 0.5
        embedding_available = False

    # --- Deterministic fallback: trigram divergence ---
    trigrams = _char_trigrams(lower)
    if len(trigrams) < 10:
        jsd = 0.5
    else:
        text_dist = _distribution(trigrams)
        jsd = _jensen_shannon_divergence(text_dist, _SLOP_TRIGRAM_DIST)
    trigram_score = clamp(jsd / 0.6)

    # --- 2. Vocabulary richness: hapax legomena ratio ---
    word_counts = Counter(words)
    total_words = len(words)
    if total_words < 5:
        hapax_ratio = 0.5
    else:
        hapax = sum(1 for c in word_counts.values() if c == 1)
        hapax_ratio = hapax / total_words  # high → more unique words

    # --- 3. Bigram novelty ---
    if len(words) < 3:
        bigram_novelty = 0.5
    else:
        bigrams = [f"{words[i]} {words[i + 1]}" for i in range(len(words) - 1)]
        unique_bigrams = len(set(bigrams))
        bigram_novelty = unique_bigrams / len(bigrams)

    # --- 4. Filler phrase penalty ---
    filler_hits = sum(1 for p in FILLER_PHRASES if p in lower)
    filler_penalty = min(filler_hits * 0.06, 0.35)

    # --- Composite score ---
    if embedding_available:
        # Production: blend embedding (60%) with trigram (20%) + linguistic signals
        raw = (
            0.60 * embedding_score
            + 0.20 * trigram_score
            + 0.15 * hapax_ratio
            + 0.10 * bigram_novelty
            - filler_penalty
        )
    else:
        # Deterministic fallback
        raw = (
            0.45 * trigram_score
            + 0.25 * hapax_ratio
            + 0.20 * bigram_novelty
            - filler_penalty
        )
    score = clamp(raw + 0.10)

    detail = (
        f"{'embedding' if embedding_available else 'jsd'}={'yes' if embedding_available else f'{jsd:.3f}'} "
        f"trigram_score={trigram_score:.2f} "
        f"hapax={hapax_ratio:.2f} bigram_novelty={bigram_novelty:.2f} "
        f"filler_hits={filler_hits}"
    )

    return SignalResult(
        name="semantic_uniqueness_proxy",
        score=round(score, 4),
        weight=1.0,
        detail=detail,
    )


# ===================================================================
# Signal 2 — human_delta_score  (NEW)
# ===================================================================

# Patterns that suggest human editing / revision
_EDITING_ARTIFACTS = [
    re.compile(r"\bactually\b", re.I),
    re.compile(r"\bwait\b", re.I),
    re.compile(r"\bcorrection:", re.I),
    re.compile(r"\bedit:", re.I),
    re.compile(r"\bupdate:", re.I),
    re.compile(r"\bstrikethrough\b", re.I),
    re.compile(r"\boops\b", re.I),
    re.compile(r"\btypo\b", re.I),
    re.compile(r"\bnvm\b", re.I),
    re.compile(r"\bnevermind\b", re.I),
    re.compile(r"\bscratch that\b", re.I),
    re.compile(r"\bon second thought\b", re.I),
    re.compile(r"~~.+~~"),  # markdown strikethrough
]

_REVISION_MARKERS = [
    re.compile(r"\boriginally\b", re.I),
    re.compile(r"\bchanged from\b", re.I),
    re.compile(r"\bwas\s+\w+\s+now\b", re.I),
    re.compile(r"\brevision\b", re.I),
    re.compile(r"\bv\d+", re.I),
    re.compile(r"\bdraft\b", re.I),
    re.compile(r"\bpreviously\b", re.I),
    re.compile(r"\bupdated to\b", re.I),
]

_UNCERTAINTY_HEDGES = [
    re.compile(r"\bi think\b", re.I),
    re.compile(r"\bprobably\b", re.I),
    re.compile(r"\bnot sure if\b", re.I),
    re.compile(r"\bmight need to\b", re.I),
    re.compile(r"\bmaybe\b", re.I),
    re.compile(r"\bi guess\b", re.I),
    re.compile(r"\bi feel like\b", re.I),
    re.compile(r"\bnot certain\b", re.I),
    re.compile(r"\bcould be wrong\b", re.I),
    re.compile(r"\bif i recall\b", re.I),
    re.compile(r"\biirc\b", re.I),
    re.compile(r"\bafaik\b", re.I),
    re.compile(r"\bimo\b", re.I),
    re.compile(r"\bimho\b", re.I),
]

_DISAGREEMENT_MARKERS = [
    re.compile(r"\bbut\b", re.I),
    re.compile(r"\bhowever\b", re.I),
    re.compile(r"\balthough\b", re.I),
    re.compile(r"\bon the other hand\b", re.I),
    re.compile(r"\bcounterpoint\b", re.I),
    re.compile(r"\bthat said\b", re.I),
    re.compile(r"\bnevertheless\b", re.I),
    re.compile(r"\bnonetheless\b", re.I),
    re.compile(r"\bstill,\b", re.I),
    re.compile(r"\beven so\b", re.I),
    re.compile(r"\bi disagree\b", re.I),
    re.compile(r"\bnot really\b", re.I),
]


def human_delta_score(text: str) -> SignalResult:
    """
    Detect signals that a human actively engaged with and modified the
    content rather than publishing raw AI output.  Higher = more human.
    """

    def _count_hits(patterns: list[re.Pattern], t: str) -> int:
        return sum(1 for p in patterns if p.search(t))

    editing = _count_hits(_EDITING_ARTIFACTS, text)
    revision = _count_hits(_REVISION_MARKERS, text)
    hedging = _count_hits(_UNCERTAINTY_HEDGES, text)
    disagreement = _count_hits(_DISAGREEMENT_MARKERS, text)

    # Questions indicate engagement
    question_count = text.count("?")

    # Exclamations / informal punctuation
    informal_punct = text.count("!") + text.count("...")

    # Contractions are more human
    contraction_count = len(re.findall(r"\b\w+'(t|s|re|ve|ll|d|m)\b", text, re.I))

    # Personal anecdotes / first-person references
    first_person = len(re.findall(r"\b(I|me|my|myself|we|us|our)\b", text))

    # Named entities: proper nouns, specific people, places, orgs
    named_entity_count = len(re.findall(r"\b[A-Z][a-zA-Z]{2,}\s+[A-Z][a-zA-Z]{2,}\b", text))

    # Direct references: "I saw", "we found", "our team", etc.
    direct_ref = len(re.findall(r"\b(I|we)\s+(saw|found|noticed|observed|tested|verified|measured|discovered|confirmed)\b", text, re.I))

    # Weighted combination — professional writing should score well without "messiness"
    raw = (
        0.15 * min(editing, 5) / 5
        + 0.12 * min(revision, 4) / 4
        + 0.10 * min(hedging, 5) / 5
        + 0.12 * min(disagreement, 5) / 5
        + 0.08 * min(question_count, 5) / 5
        + 0.04 * min(informal_punct, 4) / 4
        + 0.06 * min(contraction_count, 6) / 6
        + 0.08 * min(first_person, 8) / 8
        + 0.13 * min(named_entity_count, 6) / 6
        + 0.12 * min(direct_ref, 4) / 4
    )

    score = clamp(raw)

    detail = (
        f"editing={editing} revision={revision} hedging={hedging} "
        f"disagreement={disagreement} questions={question_count} "
        f"contractions={contraction_count} first_person={first_person} "
        f"named_entities={named_entity_count} direct_refs={direct_ref}"
    )

    return SignalResult(
        name="human_delta_score",
        score=round(score, 4),
        weight=0.3,
        detail=detail,
    )


# ===================================================================
# Signal 3 — information_density
# ===================================================================

def information_density(text: str) -> SignalResult:
    """
    Measures how much real information the text carries using Shannon
    entropy, compression-ratio proxy, sentence-level novelty progression,
    vocabulary sophistication, and filler-phrase penalties.
    """
    words = tokenize(text)
    sentences = split_sentences(text)
    lower = text.lower()
    total_words = len(words)

    if total_words < 3:
        return SignalResult(
            name="information_density",
            score=0.5,
            weight=1.0,
            detail="text too short",
        )

    # --- 1. Stop-word ratio (lower is denser) ---
    stop_count = sum(1 for w in words if w in STOP_WORDS)
    stop_ratio = stop_count / total_words
    # Typical prose: ~0.45-0.55 stop-words.  Dense text: < 0.40
    stop_score = clamp(1.0 - stop_ratio)  # invert: low stop-words → high score

    # --- 2. Shannon entropy of word distribution ---
    entropy = _shannon_entropy(words)
    # Max entropy for N unique words = log2(N).  Normalize by log2(total).
    max_possible = math.log2(total_words) if total_words > 1 else 1.0
    entropy_score = clamp(entropy / max_possible)

    # --- 3. Compression ratio proxy: unique bigrams / total bigrams ---
    if total_words >= 2:
        bigrams = [f"{words[i]} {words[i + 1]}" for i in range(total_words - 1)]
        compression_ratio = len(set(bigrams)) / len(bigrams)
    else:
        compression_ratio = 0.5

    # --- 4. Sentence-level information progression ---
    if len(sentences) >= 2:
        prev_words: set[str] = set()
        novelty_scores = []
        for sent in sentences:
            sent_words = set(tokenize(sent))
            if sent_words:
                new_words = sent_words - prev_words
                novelty = len(new_words) / len(sent_words)
                novelty_scores.append(novelty)
                prev_words |= sent_words
        avg_novelty = sum(novelty_scores) / len(novelty_scores) if novelty_scores else 0.5
    else:
        avg_novelty = 0.5

    # --- 5. Average word length (vocabulary sophistication proxy) ---
    avg_word_len = sum(len(w) for w in words) / total_words
    # Typical English avg ~4.5.  Sophisticated text ~5.5+
    word_len_score = clamp((avg_word_len - 3.0) / 4.0)

    # --- 6. Lexical diversity (type-token ratio) ---
    ttr = len(set(words)) / total_words

    # --- 7. Filler phrase penalty ---
    filler_hits = sum(1 for p in FILLER_PHRASES if p in lower)
    filler_penalty = min(filler_hits * 0.05, 0.30)

    # --- 8. Concrete patterns bonus ---
    concrete_hits = sum(len(p.findall(text)) for p in CONCRETE_PATTERNS)
    concrete_bonus = min(concrete_hits * 0.015, 0.15)

    # --- 9. Circular reasoning penalty ---
    # Detects content that repeats the same concept with different words
    # e.g., "Authentication is the process of authenticating users"
    circular_penalty = 0.0
    if len(sentences) >= 2:
        for sent in sentences:
            sent_words = set(tokenize(sent))
            if len(sent_words) < 15:
                continue
            # Check if key terms from this sentence repeat in other sentences without new info
            key_terms = {w for w in sent_words if len(w) > 4 and w not in STOP_WORDS}
            if not key_terms:
                continue
            for other in sentences:
                if other == sent:
                    continue
                other_words = set(tokenize(other))
                # High overlap with few new terms = circular
                overlap = len(key_terms & other_words) / max(len(key_terms), 1)
                new_info = len(other_words - sent_words) / max(len(other_words), 1)
                if overlap > 0.5 and new_info < 0.3:
                    circular_penalty += 0.10
    circular_penalty = min(circular_penalty, 0.40)

    # --- Composite ---
    raw = (
        0.15 * stop_score
        + 0.20 * entropy_score
        + 0.15 * compression_ratio
        + 0.15 * avg_novelty
        + 0.10 * word_len_score
        + 0.15 * ttr
        + concrete_bonus
        - filler_penalty
        - circular_penalty
    )

    score = clamp(raw + 0.05)

    detail = (
        f"stop={stop_ratio:.2f} entropy={entropy:.2f}/{max_possible:.2f} "
        f"compress={compression_ratio:.2f} novelty={avg_novelty:.2f} "
        f"avg_wl={avg_word_len:.1f} ttr={ttr:.2f} "
        f"concrete={concrete_hits} filler={filler_hits}"
    )

    return SignalResult(
        name="information_density",
        score=round(score, 4),
        weight=1.0,
        detail=detail,
    )


# ===================================================================
# Signal 4 — why_vs_what
# ===================================================================

def why_vs_what(text: str, domain: str = "general") -> SignalResult:
    """
    Measures the ratio of explanatory / justification language vs.
    simple declarative statements. Uses RoBERTa zero-shot classification
    when available (production), falling back to cue-based marker counting.
    Includes sentence-level causal classification, conditional reasoning,
    comparisons, and tradeoffs.

    Adversarial slop detection: WHY sentences are verified for specificity.
    Generic/unfalsifiable reasoning ("because it was slow") is penalized,
    while specific/falsifiable reasoning ("because profiling showed 340ms")
    retains full credit.
    """
    lower = text.lower()
    sentences = split_sentences(text)

    # --- Production: RoBERTa zero-shot classification ---
    try:
        from slopguard.adapters.roberta_whywhat import why_what_roberta_ratio
        roberta_ratio = why_what_roberta_ratio(text)
        roberta_available = roberta_ratio != 0.5 or len(sentences) < 3
    except ImportError:
        roberta_ratio = 0.5
        roberta_available = False

    # --- Deterministic fallback: marker counting ---
    why_hits = sum(1 for m in WHY_MARKERS if m in lower)
    what_hits = sum(1 for m in WHAT_MARKERS if m in lower)

    total_markers = why_hits + what_hits
    if total_markers == 0:
        marker_ratio = 0.5
    else:
        marker_ratio = why_hits / total_markers

    # --- Sentence-level classification ---
    causal_sentences = 0
    why_sentences = []
    why_confidences = []
    for sent in sentences:
        is_causal = any(p.search(sent) for p in CAUSAL_CONNECTIVES)
        if is_causal:
            causal_sentences += 1
            why_sentences.append(sent)
            # Confidence based on number of causal markers in sentence
            sent_lower = sent.lower()
            marker_count = sum(1 for m in WHY_MARKERS if m in sent_lower)
            # Base confidence of 0.75 for any causal sentence, boosted by markers
            confidence = min(0.75 + marker_count * 0.1, 1.0)
            why_confidences.append(confidence)
    causal_ratio = causal_sentences / max(len(sentences), 1)

    # --- Adversarial slop detection: specificity verification ---
    specificity_composite = 0.5
    flagged_claims = []
    strong_claims = []
    reasoning_quality = "insufficient_data"

    if why_sentences:
        from slopguard.detectors.specificity import verify_reasoning
        specificity_composite, flagged, strong = verify_reasoning(
            why_sentences, why_confidences, domain, text
        )

        # Convert ClaimVerdict to dict for JSON serialization
        flagged_claims = [
            {
                "sentence": c.sentence[:150],
                "why_confidence": c.why_confidence,
                "specificity": c.specificity,
                "verdict": c.verdict,
                "suggestion": c.suggestion,
            }
            for c in flagged
        ]
        strong_claims = [
            {
                "sentence": c.sentence[:150],
                "why_confidence": c.why_confidence,
                "specificity": c.specificity,
                "verdict": c.verdict,
            }
            for c in strong
        ]

        # Determine reasoning quality label
        if specificity_composite >= 0.7:
            reasoning_quality = "specific"
        elif specificity_composite >= 0.45:
            reasoning_quality = "mixed"
        elif specificity_composite >= 0.3:
            reasoning_quality = "qualitative"
        else:
            reasoning_quality = "unfalsifiable"
    else:
        # No WHY sentences found
        if causal_sentences == 0 and why_hits == 0:
            reasoning_quality = "no_reasoning_detected"
        else:
            reasoning_quality = "insufficient_data"

    # --- Question presence (questions suggest engagement) ---
    question_sentences = sum(1 for s in sentences if s.rstrip().endswith("?"))
    question_ratio = question_sentences / max(len(sentences), 1)

    # --- Conditional reasoning ---
    conditional_hits = sum(
        1 for p in CONDITIONAL_PATTERNS if p.search(text)
    )
    conditional_score = min(conditional_hits / 3.0, 1.0)

    # --- Comparative reasoning ---
    comparative_hits = sum(
        1 for p in COMPARATIVE_PATTERNS if p.search(text)
    )
    comparative_score = min(comparative_hits / 3.0, 1.0)

    # --- Tradeoff language ---
    tradeoff_hits = sum(
        1 for p in TRADEOFF_PATTERNS if p.search(text)
    )
    tradeoff_score = min(tradeoff_hits / 2.0, 1.0)

    # --- Depth ratio: sentences with subordinate clauses ---
    deep_sentences = 0
    for sent in sentences:
        # Commas or semicolons combined with reasoning words suggest depth
        has_structure = sent.count(",") >= 2 or ";" in sent
        has_reasoning = any(p.search(sent) for p in CAUSAL_CONNECTIVES)
        if has_structure and has_reasoning:
            deep_sentences += 1
    depth_ratio = deep_sentences / max(len(sentences), 1)

    # --- Before/after evidence patterns ---
    # Content showing quantitative before/after comparisons demonstrates reasoning
    before_after = len(re.findall(
        r"\b(before|after|pre[- ]patch|post[- ]patch|previously|originally)\b.*?\b\d+",
        lower,
    )) + len(re.findall(
        r"\b(from|down\s+from|reduced\s+from)\s+\d+.*?\b(to|down\s+to)\s+\d+",
        lower,
    ))
    evidence_progression = min(before_after / 2.0, 1.0)

    # --- Composite: use specificity-composite WHY score ---
    # Replace the raw WHY component with the specificity-blended score
    specificity_blended_why = specificity_composite

    # When causal sentences are detected (including via em-dash), treat causal_ratio
    # as a proxy for marker_ratio so em-dash reasoning gets full credit.
    effective_marker_ratio = marker_ratio if why_hits > 0 else causal_ratio

    if roberta_available:
        raw = (
            0.35 * specificity_blended_why
            + 0.13 * effective_marker_ratio
            + 0.13 * causal_ratio
            + 0.07 * question_ratio
            + 0.06 * conditional_score
            + 0.06 * comparative_score
            + 0.06 * tradeoff_score
            + 0.08 * depth_ratio
            + 0.06 * evidence_progression
        )
    else:
        raw = (
            0.22 * specificity_blended_why
            + 0.17 * causal_ratio
            + 0.09 * question_ratio
            + 0.09 * conditional_score
            + 0.09 * comparative_score
            + 0.09 * tradeoff_score
            + 0.13 * depth_ratio
            + 0.12 * evidence_progression
        )

    score = clamp(raw)

    detail = (
        f"{'roberta' if roberta_available else 'cue'} "
        f"why={why_hits} what={what_hits} causal_sent={causal_sentences}/{len(sentences)} "
        f"specificity={specificity_composite:.3f} quality={reasoning_quality} "
        f"flagged={len(flagged_claims)} strong={len(strong_claims)} "
        f"questions={question_sentences} cond={conditional_hits} "
        f"comp={comparative_hits} tradeoff={tradeoff_hits} depth={deep_sentences}"
    )

    return SignalResult(
        name="why_vs_what",
        score=round(score, 4),
        weight=1.8,
        detail=detail,
        specificity_score=round(specificity_composite, 3),
        reasoning_quality=reasoning_quality,
        flagged_claims=flagged_claims,
        strong_claims=strong_claims,
    )


# ===================================================================
# Signal 5 — template_structure
# ===================================================================

def template_structure(text: str) -> SignalResult:
    """
    Detect templated / formulaic structure typical of AI-generated text.
    Lower score = more templated.  Higher score = more organic.

    Checks: sentence-length variation, opener repetition, n-gram patterns,
    bullet/list patterns, paragraph uniformity, AI transition phrases,
    sentence complexity variation, and voice consistency.
    """
    sentences = split_sentences(text)
    words = tokenize(text)
    lower = text.lower()

    if len(sentences) < 3:
        return SignalResult(
            name="template_structure",
            score=0.5,
            weight=1.0,
            detail="text too short for structure analysis",
        )

    # --- 1. Sentence length CoV (low CoV → templated) ---
    lengths = [len(tokenize(s)) for s in sentences]
    mean_len = sum(lengths) / len(lengths)
    if mean_len > 0:
        variance = sum((l - mean_len) ** 2 for l in lengths) / len(lengths)
        std_dev = math.sqrt(variance)
        cov = std_dev / mean_len
    else:
        cov = 0.0
    # Natural writing: CoV ~0.4-0.8.  Templated: ~0.1-0.25
    cov_score = clamp((cov - 0.1) / 0.6)

    # --- 2. Repeated sentence openers ---
    openers = []
    for s in sentences:
        s_words = tokenize(s)
        if len(s_words) >= 3:
            openers.append(" ".join(s_words[:3]))
        elif len(s_words) >= 1:
            openers.append(" ".join(s_words[:1]))
    opener_counts = Counter(openers)
    repeated_openers = sum(c - 1 for c in opener_counts.values() if c > 1)
    opener_penalty = min(repeated_openers * 0.08, 0.40)

    # --- 3. First-3-word n-gram pattern detection ---
    first_words = []
    for s in sentences:
        s_words = tokenize(s)
        if s_words:
            first_words.append(s_words[0])
    first_word_counts = Counter(first_words)
    dominant_first = max(first_word_counts.values()) if first_word_counts else 0
    first_word_repetition = dominant_first / max(len(sentences), 1)
    # If > 40% of sentences start with the same word, it's formulaic
    first_word_penalty = clamp((first_word_repetition - 0.3) / 0.4) * 0.15

    # --- 4. Bullet / list pattern detection ---
    bullet_lines = len(re.findall(r"^\s*[-*•]\s", text, re.MULTILINE))
    numbered_lines = len(re.findall(r"^\s*\d+[.)]\s", text, re.MULTILINE))
    total_lines = max(text.count("\n") + 1, 1)
    list_ratio = (bullet_lines + numbered_lines) / total_lines
    # Some lists are fine; heavy list usage is templated
    list_penalty = clamp((list_ratio - 0.3) / 0.5) * 0.15

    # --- 5. Paragraph length uniformity ---
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    if len(paragraphs) >= 3:
        para_lengths = [len(p) for p in paragraphs]
        para_mean = sum(para_lengths) / len(para_lengths)
        if para_mean > 0:
            para_var = sum((l - para_mean) ** 2 for l in para_lengths) / len(para_lengths)
            para_cov = math.sqrt(para_var) / para_mean
        else:
            para_cov = 0.0
        # Low paragraph CoV → suspiciously uniform
        para_score = clamp((para_cov - 0.05) / 0.5)
    else:
        para_score = 0.5

    # --- 6. AI transition phrase detection ---
    transition_hits = 0
    for phrase in AI_TRANSITIONS:
        if phrase in lower:
            transition_hits += 1
    transition_penalty = min(transition_hits * 0.06, 0.30)

    # --- 7. Sentence complexity variation ---
    complexity_scores = []
    for s in sentences:
        comma_count = s.count(",")
        semi_count = s.count(";")
        paren_count = s.count("(")
        complexity = comma_count + semi_count * 2 + paren_count * 1.5
        complexity_scores.append(complexity)
    if len(complexity_scores) >= 2:
        c_mean = sum(complexity_scores) / len(complexity_scores)
        if c_mean > 0:
            c_var = sum((c - c_mean) ** 2 for c in complexity_scores) / len(complexity_scores)
            c_cov = math.sqrt(c_var) / c_mean
        else:
            c_cov = 0.0
        complexity_variation_score = clamp(c_cov / 1.5)
    else:
        complexity_variation_score = 0.5

    # --- 8. Voice consistency: personal vs impersonal ratio ---
    personal_pronouns = len(
        re.findall(r"\b(I|me|my|we|us|our|you|your)\b", text, re.I)
    )
    impersonal = len(
        re.findall(r"\b(it is|there is|there are|one should|one can|this is)\b", text, re.I)
    )
    total_voice = personal_pronouns + impersonal
    if total_voice > 0:
        personal_ratio = personal_pronouns / total_voice
    else:
        personal_ratio = 0.5
    # Extreme impersonality is AI-like; mix is more human
    voice_score = clamp(personal_ratio * 1.2)

    # --- Composite (higher = more organic / less templated) ---
    raw = (
        0.20 * cov_score
        + 0.10 * para_score
        + 0.15 * complexity_variation_score
        + 0.10 * voice_score
        - opener_penalty
        - first_word_penalty
        - list_penalty
        - transition_penalty
    )

    score = clamp(raw + 0.35)  # shift so neutral text lands near 0.5

    detail = (
        f"cov={cov:.2f} openers_rep={repeated_openers} first_rep={first_word_repetition:.2f} "
        f"lists={bullet_lines + numbered_lines}/{total_lines} para_cov={para_score:.2f} "
        f"ai_transitions={transition_hits} complexity_cov={complexity_variation_score:.2f} "
        f"voice_personal={personal_ratio:.2f}"
    )

    return SignalResult(
        name="template_structure",
        score=round(score, 4),
        weight=1.0,
        detail=detail,
    )


# ===================================================================
# Signal 6 — specificity (unchanged logic)
# ===================================================================

def specificity(text: str) -> SignalResult:
    """
    Percentage of sentences that contain at least one concrete technical
    reference (number, camelCase identifier, inline code, filename, or
    system-level keyword).
    """
    sentences = split_sentences(text)
    if not sentences:
        return SignalResult(
            name="specificity",
            score=0.5,
            weight=1.2,
            detail="no sentences",
        )
    concrete = 0
    for s in sentences:
        if any(p.search(s) for p in CONCRETE_PATTERNS):
            concrete += 1
    ratio = concrete / len(sentences)
    return SignalResult(
        name="specificity",
        score=round(clamp(ratio), 4),
        weight=1.8,
        detail=f"{concrete}/{len(sentences)} sentences with concrete refs",
    )


# ===================================================================
# Signal 7 — evidence_density (NEW)
# Penalizes technical jargon used without supporting measurements/evidence
# ===================================================================

_JARGON_TERMS = {
    "optimized", "performance", "efficiency", "scalable", "scalability",
    "robust", "resilient", "reliable", "maintainable", "flexible",
    "modular", "extensible", "elegant", "clean", "sophisticated",
    "enterprise-grade", "production-ready", "battle-tested", "hardened",
    "streamlined", "best-in-class", "world-class", "cutting-edge",
    "innovative", "transformative", "revolutionary", "disruptive",
    "synergistic", "holistic", "comprehensive", "end-to-end",
    "query planner", "query optimizer", "execution plan", "index scan",
    "covering index", "composite index", "b-tree", "hash index",
    "connection pool", "thread pool", "goroutine", "async", "non-blocking",
    "event-driven", "reactive", "microservice", "service mesh",
    "load balancer", "circuit breaker", "rate limiter", "throttling",
    "caching layer", "in-memory cache", "distributed cache",
    "data pipeline", "stream processing", "batch processing",
    "machine learning", "deep learning", "neural network", "AI-powered",
    "intelligent", "smart", "automated", "self-healing", "self-optimizing",
}

_EVIDENCE_MARKERS = {
    # Numeric evidence
    re.compile(r"\b\d+(\.\d+)?\s*(?:ms|s|sec|min|hr|mb|gb|tb|%|x|times|rps|ops|qps|fps)\b", re.I),
    re.compile(r"\b\d{2,}[,\.]\d{3,}\b"),  # Large numbers: 10,000
    re.compile(r"\b[Pp]\d{2,}\b"),  # P95, P99
    # Comparative with numbers
    re.compile(r"(?:reduced|decreased|improved|increased|dropped|grew|cut|saved|sped)\s+(?:by\s+)?\d+", re.I),
    re.compile(r"(?:from|down\s+from)\s+\d+\s+(?:to|down\s+to)\s+\d+", re.I),
    # Tool output / benchmark references
    re.compile(r"(?:bench|profil|flamegraph|perf|test|load\s*test)\s*(?:show|indicate|reveal|measur)", re.I),
    # Concrete before/after
    re.compile(r"(?:before|after|pre[- ]patch|post[- ]patch)\s*:\s*\d+", re.I),
}

def evidence_density(text: str) -> SignalResult:
    """
    Detects technical jargon used WITHOUT supporting evidence.
    Content that uses performance/optimization language but provides
    no numbers, benchmarks, or measurements is penalized heavily.
    Higher score = claims are backed by evidence.
    """
    lower = text.lower()
    sentences = split_sentences(text)
    if len(sentences) < 2:
        return SignalResult(
            name="evidence_density",
            score=0.5,
            weight=0.8,
            detail="text too short for evidence analysis",
        )

    # Count jargon sentences
    jargon_sentences = 0
    evidence_sentences = 0
    jargon_evidence_sentences = 0

    for s in sentences:
        s_lower = s.lower()
        has_jargon = any(term in s_lower for term in _JARGON_TERMS)
        has_evidence = any(p.search(s) for p in _EVIDENCE_MARKERS)

        if has_jargon:
            jargon_sentences += 1
            if has_evidence:
                jargon_evidence_sentences += 1
        if has_evidence:
            evidence_sentences += 1

    if jargon_sentences == 0:
        # No jargon detected — neutral score, slight bonus for evidence
        score = clamp(0.55 + min(evidence_sentences * 0.08, 0.30))
        detail = f"no_jargon evidence_sents={evidence_sentences}/{len(sentences)}"
    else:
        # Ratio of jargon sentences that ARE backed by evidence
        evidence_ratio = jargon_evidence_sentences / jargon_sentences
        # Penalty: if jargon exists but NO evidence, score drops sharply
        score = clamp(evidence_ratio * 0.8 + 0.15)
        detail = (
            f"jargon_sents={jargon_sentences}/{len(sentences)} "
            f"evidence_backed={jargon_evidence_sentences} "
            f"ratio={evidence_ratio:.2f} total_evidence={evidence_sentences}"
        )

    return SignalResult(
        name="evidence_density",
        score=round(score, 4),
        weight=1.0,
        detail=detail,
    )


# ===================================================================
# Aggregator
# ===================================================================

def universal_signals(text: str, domain: str = "general") -> list[SignalResult]:
    """Return all universal signal results for the given text.
    
    Now includes three novel signals that are hard to fake:
    1. Epistemic Cowardice — detects systematic avoidance of taking positions
    2. Counterfactual Absence — detects missing alternatives, failure modes, tradeoffs
    3. Vocabulary Novelty — detects flat vs progressive vocabulary introduction curves
    """
    return [
        semantic_uniqueness_proxy(text),
        human_delta_score(text),
        information_density(text),
        why_vs_what(text, domain),
        template_structure(text),
        specificity(text),
        evidence_density(text),
        # Three novel signals — Sharpest Signal prize contenders
        epistemic_cowardice_signal(text),
        counterfactual_absence_signal(text),
        vocabulary_novelty_signal(text),
    ]
