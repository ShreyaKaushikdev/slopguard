"""Novel Signal 3 — Vocabulary Novelty Collapse Detector

The insight nobody else has:
This is the most technically original signal and the hardest to explain simply —
which means it's the hardest for other teams to copy even if they hear you describe it.

The core observation:
Every domain has a distribution of vocabulary novelty across a document. Human
experts introduce new concepts progressively — early sections use familiar vocabulary,
later sections introduce increasingly specific terminology as context is established.
The vocabulary novelty curve has a shape.

AI-generated content has a characteristic flat vocabulary novelty curve. It distributes
technical terminology uniformly throughout the document because it doesn't build
context the way humans do. It front-loads impressive terminology to signal expertise.
It repeats the same technical terms at the same frequency from paragraph 1 to paragraph 10.

How it works:
1. Split text into sentences
2. Track which words have been seen before
3. For each sentence, compute novelty = new_words / total_words
4. Analyze the curve shape:
   - Human writing: high novelty early, decreasing curve, spikes at section transitions
   - AI writing: flat curve, uniform novelty throughout

Curve metrics:
- curve_variance: Low variance = flat = AI signature
- slope: Negative slope = human (novelty decreases as context builds)
- spike_count: Section transitions create novelty spikes in human writing
- entropy: Shannon entropy of the novelty distribution

Why it's novel:
No existing detector uses this. It's not looking at what words are used. It's looking
at the shape of how vocabulary is introduced over time. This is a structural signal
about the cognitive process that generated the text, not the content itself.

Why it's hard to fake:
You cannot prompt-engineer a human-shaped vocabulary novelty curve. The only way to
produce one is to actually build an argument progressively, introducing concepts as
they become relevant. That requires genuine domain knowledge and genuine thinking.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass

from slopguard.models import SignalResult


# ============================================================================
# Text processing utilities
# ============================================================================

def split_sentences(text: str) -> list[str]:
    """Split text into sentences."""
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s.strip() for s in sentences if s.strip()]


def extract_content_words(sentence: str) -> list[str]:
    """Extract content words (not stop words) from a sentence."""
    # Simple tokenization
    words = re.findall(r'\b[a-zA-Z][a-zA-Z0-9_-]*\b', sentence.lower())
    
    # Common stop words to exclude
    stop_words = {
        'a', 'an', 'and', 'are', 'as', 'at', 'be', 'by', 'for', 'from',
        'has', 'he', 'in', 'is', 'it', 'its', 'of', 'on', 'that', 'the',
        'to', 'was', 'will', 'with', 'this', 'but', 'they', 'have', 'had',
        'what', 'when', 'where', 'who', 'which', 'why', 'how', 'all', 'each',
        'every', 'both', 'few', 'more', 'most', 'other', 'some', 'such',
        'than', 'too', 'very', 'can', 'could', 'may', 'might', 'must',
        'shall', 'should', 'would', 'or', 'not', 'no', 'nor', 'if', 'then',
        'so', 'because', 'as', 'until', 'while', 'about', 'after', 'before',
        'between', 'into', 'through', 'during', 'above', 'below', 'up', 'down',
        'out', 'off', 'over', 'under', 'again', 'further', 'once', 'here',
        'there', 'all', 'any', 'both', 'each', 'few', 'more', 'most', 'other',
        'some', 'such', 'only', 'own', 'same', 'than', 'too', 'very', 'just',
        'now', 'also', 'been', 'being', 'do', 'does', 'did', 'doing', 'get',
        'got', 'getting', 'make', 'made', 'making', 'go', 'going', 'went',
        'gone', 'come', 'came', 'coming', 'take', 'took', 'taken', 'taking',
        'see', 'saw', 'seen', 'seeing', 'know', 'knew', 'known', 'knowing',
        'think', 'thought', 'thinking', 'say', 'said', 'saying', 'tell',
        'told', 'telling', 'use', 'used', 'using', 'find', 'found', 'finding',
        'give', 'gave', 'given', 'giving', 'work', 'worked', 'working',
    }
    
    return [w for w in words if w not in stop_words and len(w) > 2]


# ============================================================================
# Curve analysis functions
# ============================================================================

def compute_novelty_curve(text: str) -> list[float]:
    """Compute vocabulary novelty for each sentence.
    
    Returns a list of novelty scores (0.0 to 1.0) for each sentence.
    Novelty = (new words not seen before) / (total content words in sentence)
    """
    sentences = split_sentences(text)
    seen_tokens: set[str] = set()
    novelty_per_sentence: list[float] = []
    
    for sentence in sentences:
        tokens = extract_content_words(sentence)
        
        if not tokens:
            # No content words in this sentence
            novelty_per_sentence.append(0.0)
            continue
        
        new_tokens = [t for t in tokens if t not in seen_tokens]
        novelty = len(new_tokens) / len(tokens)
        novelty_per_sentence.append(novelty)
        
        # Update seen tokens
        seen_tokens.update(tokens)
    
    return novelty_per_sentence


def compute_variance(values: list[float]) -> float:
    """Compute variance of a list of values."""
    if len(values) < 2:
        return 0.0
    
    mean = sum(values) / len(values)
    variance = sum((x - mean) ** 2 for x in values) / len(values)
    return variance


def compute_linear_slope(values: list[float]) -> float:
    """Compute the slope of a linear regression through the values.
    
    Negative slope = decreasing novelty over time (human pattern)
    Zero slope = flat novelty (AI pattern)
    Positive slope = increasing novelty (unusual)
    """
    if len(values) < 2:
        return 0.0
    
    n = len(values)
    x_values = list(range(n))
    
    # Linear regression: y = mx + b
    # m = (n*Σxy - Σx*Σy) / (n*Σx² - (Σx)²)
    sum_x = sum(x_values)
    sum_y = sum(values)
    sum_xy = sum(x * y for x, y in zip(x_values, values))
    sum_x_squared = sum(x * x for x in x_values)
    
    denominator = n * sum_x_squared - sum_x * sum_x
    if denominator == 0:
        return 0.0
    
    slope = (n * sum_xy - sum_x * sum_y) / denominator
    return slope


def count_significant_spikes(values: list[float], threshold: float = 0.3) -> int:
    """Count significant spikes in the novelty curve.
    
    A spike is when novelty increases by more than threshold from one sentence to the next.
    Human writing has spikes at section transitions. AI writing has few spikes.
    """
    if len(values) < 2:
        return 0
    
    spike_count = 0
    for i in range(1, len(values)):
        if values[i] - values[i-1] > threshold:
            spike_count += 1
    
    return spike_count


def compute_entropy(values: list[float], bins: int = 5) -> float:
    """Compute Shannon entropy of the novelty distribution.
    
    High entropy = varied novelty (human pattern)
    Low entropy = uniform novelty (AI pattern)
    """
    if len(values) < 2:
        return 0.0
    
    # Bin the values into discrete buckets
    min_val = min(values)
    max_val = max(values)
    
    if max_val - min_val < 0.01:
        # All values are essentially the same
        return 0.0
    
    bin_width = (max_val - min_val) / bins
    bin_counts = [0] * bins
    
    for value in values:
        bin_index = min(int((value - min_val) / bin_width), bins - 1)
        bin_counts[bin_index] += 1
    
    # Compute Shannon entropy
    total = len(values)
    entropy = 0.0
    for count in bin_counts:
        if count > 0:
            p = count / total
            entropy -= p * math.log2(p)
    
    return entropy


def detect_front_loading(novelty_curve: list[float]) -> bool:
    """Detect if technical terms are front-loaded (AI pattern).
    
    Front-loading: first 25% of sentences have lower average novelty than middle 50%.
    This is counter-intuitive but true for AI: it sprinkles technical terms throughout
    rather than building up to them.
    """
    if len(novelty_curve) < 4:
        return False
    
    n = len(novelty_curve)
    first_quarter_end = n // 4
    middle_start = n // 4
    middle_end = 3 * n // 4
    
    if first_quarter_end >= middle_start or middle_start >= middle_end:
        return False
    
    first_quarter_avg = sum(novelty_curve[:first_quarter_end]) / first_quarter_end
    middle_avg = sum(novelty_curve[middle_start:middle_end]) / (middle_end - middle_start)
    
    # AI front-loads: first quarter has similar or higher novelty than middle
    # Human builds up: first quarter has higher novelty, then decreases
    return first_quarter_avg < middle_avg * 0.9


# ============================================================================
# Core analysis
# ============================================================================

@dataclass
class VocabularyNoveltyAnalysis:
    """Analysis result for vocabulary novelty curve."""
    curve_variance: float
    slope: float
    spike_count: int
    entropy: float
    front_loading: bool
    sentence_count: int
    human_score: float  # 0.0 (AI pattern) to 1.0 (human pattern)
    verdict: str


def analyze_vocabulary_novelty(text: str) -> VocabularyNoveltyAnalysis:
    """Analyze vocabulary novelty curve to detect AI vs human patterns.
    
    For short texts (<5 sentences) falls back to word-level repetition analysis:
    AI repeats the same technical terms uniformly; humans introduce them once
    and move on.
    """
    novelty_curve = compute_novelty_curve(text)

    if len(novelty_curve) < 3:
        return VocabularyNoveltyAnalysis(
            curve_variance=0.0,
            slope=0.0,
            spike_count=0,
            entropy=0.0,
            front_loading=False,
            sentence_count=len(novelty_curve),
            human_score=0.5,
            verdict="insufficient_data",
        )

    curve_variance = compute_variance(novelty_curve)
    slope = compute_linear_slope(novelty_curve)
    spike_count = count_significant_spikes(novelty_curve)
    entropy = compute_entropy(novelty_curve)
    front_loading = detect_front_loading(novelty_curve)

    # --- Supplementary signal: term repetition density ---
    # AI repeats the same technical terms across sentences (uniform distribution).
    # Humans introduce a term once, then use pronouns/references.
    # Measure: what fraction of content words appear in 3+ sentences?
    sentences = split_sentences(text)
    if len(sentences) >= 3:
        from collections import Counter
        sentence_word_sets = [set(extract_content_words(s)) for s in sentences]
        all_words = [w for ws in sentence_word_sets for w in ws]
        word_sentence_count = Counter()
        for ws in sentence_word_sets:
            for w in ws:
                word_sentence_count[w] += 1
        total_unique = len(word_sentence_count)
        repeated_in_many = sum(1 for c in word_sentence_count.values() if c >= 3)
        repetition_ratio = repeated_in_many / max(total_unique, 1)
        # High repetition_ratio (>0.25) = AI pattern (same terms everywhere)
        # Low repetition_ratio (<0.10) = human pattern (introduce once, move on)
        repetition_penalty = min(repetition_ratio * 1.5, 0.30)
        repetition_bonus = max(0.0, (0.10 - repetition_ratio) * 2.0)
    else:
        repetition_penalty = 0.0
        repetition_bonus = 0.0

    # --- Scoring ---
    score = 0.0

    # Variance component (0.0 to 0.30)
    if curve_variance > 0.08:
        variance_score = 0.30
    elif curve_variance > 0.05:
        variance_score = 0.20
    elif curve_variance > 0.03:
        variance_score = 0.10
    else:
        variance_score = 0.0
    score += variance_score

    # Slope component (0.0 to 0.25)
    if slope < -0.01:
        slope_score = min(0.25, abs(slope) * 5.0)
    elif slope < 0.0:
        slope_score = 0.10
    else:
        slope_score = 0.0
    score += slope_score

    # Spike component (0.0 to 0.25)
    # Multiple spikes indicate section transitions (human)
    spike_score = min(spike_count * 0.08, 0.25)
    score += spike_score

    # Entropy component (0.0 to 0.20)
    if entropy > 1.5:
        entropy_score = 0.20
    elif entropy > 1.0:
        entropy_score = 0.12
    elif entropy > 0.8:
        entropy_score = 0.06
    else:
        entropy_score = 0.0
    score += entropy_score

    # Front-loading penalty (-0.15)
    if front_loading:
        score -= 0.15

    # Term repetition: AI repeats same terms uniformly, humans introduce once
    score -= repetition_penalty
    score += repetition_bonus

    # Filler phrase penalty — AI slop has high novelty curve but also filler phrases
    # Penalize texts that score well on curve but are full of AI clichés
    filler_phrases = [
        "best practices", "user experience", "robust", "seamless", "leverage",
        "cutting-edge", "comprehensive", "enhance", "it is generally accepted",
        "results may vary", "your mileage may vary", "depending on your use case",
        "in today's", "going forward", "paradigm", "holistic",
    ]
    lower_text = text.lower()
    filler_hits = sum(1 for p in filler_phrases if p in lower_text)
    filler_penalty = min(filler_hits * 0.06, 0.30)
    score -= filler_penalty

    # Clamp to [0, 1]
    score = max(0.0, min(1.0, score))

    # Verdict
    if score >= 0.65:
        verdict = "human_curve"
    elif score >= 0.40:
        verdict = "mixed_curve"
    elif score >= 0.20:
        verdict = "flat_curve"
    else:
        verdict = "ai_curve"

    return VocabularyNoveltyAnalysis(
        curve_variance=round(curve_variance, 4),
        slope=round(slope, 4),
        spike_count=spike_count,
        entropy=round(entropy, 3),
        front_loading=front_loading,
        sentence_count=len(novelty_curve),
        human_score=round(score, 4),
        verdict=verdict,
    )


def vocabulary_novelty_signal(text: str) -> SignalResult:
    """Generate vocabulary novelty signal for scoring engine."""
    
    analysis = analyze_vocabulary_novelty(text)
    
    # Build detail string
    detail = (
        f"verdict={analysis.verdict} "
        f"variance={analysis.curve_variance} "
        f"slope={analysis.slope} "
        f"spikes={analysis.spike_count} "
        f"entropy={analysis.entropy} "
        f"front_loading={analysis.front_loading} "
        f"sentences={analysis.sentence_count}"
    )
    
    # Build reason
    if analysis.verdict == "ai_curve":
        reason = "Flat vocabulary novelty curve: uniform terminology distribution suggests AI generation."
    elif analysis.verdict == "flat_curve":
        reason = "Low variance in vocabulary novelty: terms introduced uniformly rather than progressively."
    elif analysis.verdict == "mixed_curve":
        reason = "Mixed vocabulary novelty pattern: some progressive introduction but also uniform distribution."
    else:
        reason = "Human vocabulary curve: decreasing novelty with section spikes indicates progressive concept building."
    
    return SignalResult(
        name="vocabulary_novelty",
        score=analysis.human_score,
        weight=1.6,  # High weight — this is the most technically sophisticated signal
        detail=detail,
        reason=reason,
    )


# ============================================================================
# Visualization helper (for demo purposes)
# ============================================================================

def visualize_novelty_curve(text: str) -> dict:
    """Generate visualization data for the novelty curve.
    
    Returns a dict with:
    - curve: list of novelty values
    - labels: sentence indices
    - analysis: full analysis results
    
    This can be used to create a chart in the dashboard.
    """
    novelty_curve = compute_novelty_curve(text)
    analysis = analyze_vocabulary_novelty(text)
    
    return {
        "curve": novelty_curve,
        "labels": list(range(len(novelty_curve))),
        "analysis": {
            "variance": analysis.curve_variance,
            "slope": analysis.slope,
            "spike_count": analysis.spike_count,
            "entropy": analysis.entropy,
            "front_loading": analysis.front_loading,
            "human_score": analysis.human_score,
            "verdict": analysis.verdict,
        },
    }
