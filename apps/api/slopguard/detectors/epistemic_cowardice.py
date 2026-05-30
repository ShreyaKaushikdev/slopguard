"""Novel Signal 1 — Epistemic Cowardice Detector

The insight nobody else has:
AI doesn't just write slop. AI systematically avoids taking positions. It hedges
everything. It presents "both sides." It never commits to a recommendation.
This is epistemic cowardice — the appearance of thoughtfulness without any
actual judgment.

Humans with domain expertise make definitive claims. They say "don't do X" not
"X has tradeoffs that depend on your use case." They say "this approach is wrong
because Y" not "this approach may have limitations in certain scenarios."

What it detects:
- Hedge clustering: "may", "might", "could", "potentially", "in some cases",
  "depending on" — more than 2 per paragraph
- False balance: "on one hand... on the other hand" with no resolution
- Responsibility deflection: "it depends", "your mileage may vary",
  "consult an expert" as conclusion rather than as caveat
- Commitment absence: document makes zero falsifiable predictions or recommendations
- Opinion laundering: "some people believe", "many experts say",
  "it is generally accepted" — attributing claims to nobody specific

Why it's hard to fake:
To score well you have to actually commit to something. You have to say "do this,
not that" with a reason. AI systems are trained to be helpful to everyone which
means committing to nothing. This signal catches that systematic avoidance.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from slopguard.models import SignalResult


# ============================================================================
# Hedge words and phrases
# ============================================================================

HEDGE_WORDS = {
    "may", "might", "could", "can", "would", "should", "possibly", "perhaps",
    "potentially", "likely", "unlikely", "probably", "sometimes", "often",
    "generally", "typically", "usually", "somewhat", "relatively", "fairly",
    "rather", "quite", "mostly", "largely", "mainly", "primarily",
}

HEDGE_PHRASES = [
    re.compile(r"\bin some cases\b", re.I),
    re.compile(r"\bdepending on\b", re.I),
    re.compile(r"\bit depends\b", re.I),
    re.compile(r"\byour mileage may vary\b", re.I),
    re.compile(r"\bymmv\b", re.I),
    re.compile(r"\bconsult (?:an? )?(?:expert|professional|specialist)\b", re.I),
    re.compile(r"\bseek (?:professional )?(?:advice|guidance|help)\b", re.I),
    re.compile(r"\bmay (?:or may )?not\b", re.I),
    re.compile(r"\bcould (?:or could )?not\b", re.I),
    re.compile(r"\bmight (?:or might )?not\b", re.I),
    re.compile(r"\bin certain (?:cases|scenarios|situations|conditions)\b", re.I),
    re.compile(r"\bunder certain (?:circumstances|conditions)\b", re.I),
    re.compile(r"\bthis (?:may|might|could) (?:vary|differ|change)\b", re.I),
    re.compile(r"\bresults may vary\b", re.I),
    re.compile(r"\bnot (?:always|necessarily)\b", re.I),
    re.compile(r"\bthere(?:'s| is) no (?:one[- ]size[- ]fits[- ]all|silver bullet|magic bullet)\b", re.I),
]

# ============================================================================
# False balance patterns
# ============================================================================

FALSE_BALANCE_PATTERNS = [
    re.compile(r"\bon (?:the )?one hand\b.{10,300}\bon (?:the )?other hand\b", re.I | re.DOTALL),
    re.compile(r"\bpros and cons\b", re.I),
    re.compile(r"\badvantages and disadvantages\b", re.I),
    re.compile(r"\bbenefits and drawbacks\b", re.I),
    re.compile(r"\bupsides and downsides\b", re.I),
    re.compile(r"\bsome (?:people|experts|developers|users) (?:say|think|believe|argue)\b.{10,200}\b(?:others|however|but)\b", re.I | re.DOTALL),
]

# Patterns that indicate resolution/commitment after presenting both sides
RESOLUTION_PATTERNS = [
    re.compile(r"\b(?:therefore|thus|hence|so|consequently),? (?:I|we) (?:recommend|suggest|advise|prefer|choose)\b", re.I),
    re.compile(r"\b(?:my|our) (?:recommendation|suggestion|advice|preference) is\b", re.I),
    re.compile(r"\b(?:you|we) should (?:use|choose|prefer|go with|pick)\b", re.I),
    re.compile(r"\b(?:don't|do not|avoid|never) (?:use|do|try)\b", re.I),
    re.compile(r"\bthe (?:best|better|right|correct) (?:approach|choice|option|solution) is\b", re.I),
]

# ============================================================================
# Opinion laundering patterns
# ============================================================================

OPINION_LAUNDERING = [
    re.compile(r"\bsome (?:people|experts|developers|users|researchers|studies) (?:say|think|believe|argue|suggest|claim)\b", re.I),
    re.compile(r"\bmany (?:people|experts|developers|users|researchers|studies) (?:say|think|believe|argue|suggest|claim)\b", re.I),
    re.compile(r"\bit is (?:generally|widely|commonly|often) (?:accepted|believed|thought|considered|known)\b", re.I),
    re.compile(r"\bthere is (?:a )?(?:general )?(?:consensus|agreement) that\b", re.I),
    re.compile(r"\bmost (?:people|experts|developers|users) (?:agree|believe|think)\b", re.I),
    re.compile(r"\bthe (?:general|common|prevailing) (?:consensus|opinion|view|belief) is\b", re.I),
    re.compile(r"\bit has been (?:said|suggested|argued|claimed) that\b", re.I),
    re.compile(r"\baccording to (?:some|many|most) (?:sources|experts|studies)\b", re.I),
]

# ============================================================================
# Commitment patterns (positive signals)
# ============================================================================

COMMITMENT_PATTERNS = [
    # Direct recommendations — "I recommend", "we suggest", "use X instead"
    re.compile(r"\b(?:I|we) (?:recommend|suggest|advise|prefer|choose|decided|chose)\b", re.I),
    re.compile(r"\byou should (?:use|do|try|avoid|never|switch|migrate|pick|go with)\b", re.I),
    re.compile(r"\b(?:don't|do not|never|stop) (?:use|do|try|rely on|depend on)\b", re.I),
    re.compile(r"\balways (?:use|do|check|verify|test|prefer|choose)\b", re.I),
    re.compile(r"\buse .{3,60} instead\b", re.I),
    re.compile(r"\bswitch to\b", re.I),
    re.compile(r"\bmigrate (?:to|away from)\b", re.I),
    re.compile(r"\breplace .{3,60} with\b", re.I),

    # Definitive statements
    re.compile(r"\bthis (?:is|will|does) (?:the )?(?:best|better|right|correct|wrong|incorrect)\b", re.I),
    re.compile(r"\bthe (?:only|best|right|correct) (?:way|approach|solution|method) (?:is|to)\b", re.I),
    re.compile(r"\b(?:this|that) (?:will|won't|does|doesn't) work (?:because|when|if)\b", re.I),
    re.compile(r"\bthis (?:is|was) (?:a )?(?:mistake|error|wrong|bad idea|poor choice|anti-?pattern)\b", re.I),

    # Falsifiable predictions with numbers/specifics
    re.compile(r"\bthis will (?:cause|result in|lead to|produce|increase|decrease|break)\b", re.I),
    re.compile(r"\bcaused (?:a )?\d+", re.I),  # "caused a 3x increase"
    re.compile(r"\bexhausted at \d+", re.I),    # "exhausted at 400 concurrent users"
    re.compile(r"\b\d+x (?:increase|decrease|slower|faster)\b", re.I),
    re.compile(r"\bexpect .{5,50} to (?:increase|decrease|improve|degrade|fail)\b", re.I),

    # Strong positions with evidence
    re.compile(r"\b(?:avoid|never use|don't use|do not use) .{3,60} because\b", re.I),
    re.compile(r"\binstead[,—] (?:use|do|try|go with)\b", re.I),
    re.compile(r"\b(?:it's|it is) (?:more|less) .{3,40} but\b", re.I),  # "it's more verbose but..."
    re.compile(r"\bwe tried .{3,60} and it\b", re.I),  # "we tried X and it caused..."
    re.compile(r"\bthe (?:connection|thread|memory|request) (?:pool|limit|budget) (?:exhausted|saturated|maxed)\b", re.I),
]


# ============================================================================
# Core detection functions
# ============================================================================

@dataclass
class EpistemicCowardiceAnalysis:
    """Analysis result for epistemic cowardice detection."""
    hedge_density: float  # Hedges per 100 words
    hedge_clustering: int  # Max hedges in any single paragraph
    false_balance_count: int  # "On one hand... other hand" without resolution
    has_resolution: bool  # Does false balance have a resolution?
    opinion_laundering_count: int  # "Some people say..." attributions
    commitment_count: int  # Definitive recommendations/predictions
    responsibility_deflection: int  # "It depends", "consult expert" as conclusion
    score: float  # 0.0 (cowardly) to 1.0 (committed)
    verdict: str  # "committed", "balanced", "hedged", "cowardly"


def split_paragraphs(text: str) -> list[str]:
    """Split text into paragraphs."""
    paragraphs = re.split(r'\n\s*\n', text.strip())
    return [p.strip() for p in paragraphs if p.strip()]


def count_hedge_clustering(text: str) -> tuple[float, int]:
    """Count hedge density and maximum clustering in any paragraph.
    
    Returns (hedge_density_per_100_words, max_hedges_in_paragraph)
    """
    words = text.split()
    total_words = len(words)
    
    if total_words == 0:
        return 0.0, 0
    
    # Count total hedges
    word_set = set(w.lower().strip('.,!?;:') for w in words)
    hedge_word_count = len(word_set & HEDGE_WORDS)
    hedge_phrase_count = sum(1 for p in HEDGE_PHRASES if p.search(text))
    total_hedges = hedge_word_count + hedge_phrase_count
    
    hedge_density = (total_hedges / total_words) * 100
    
    # Check clustering per paragraph
    paragraphs = split_paragraphs(text)
    max_clustering = 0
    
    for para in paragraphs:
        para_words = para.split()
        para_word_set = set(w.lower().strip('.,!?;:') for w in para_words)
        para_hedge_words = len(para_word_set & HEDGE_WORDS)
        para_hedge_phrases = sum(1 for p in HEDGE_PHRASES if p.search(para))
        para_hedges = para_hedge_words + para_hedge_phrases
        max_clustering = max(max_clustering, para_hedges)
    
    return hedge_density, max_clustering


def detect_false_balance(text: str) -> tuple[int, bool]:
    """Detect false balance patterns and whether they have resolution.
    
    Returns (false_balance_count, has_resolution)
    """
    false_balance_count = sum(1 for p in FALSE_BALANCE_PATTERNS if p.search(text))
    
    if false_balance_count == 0:
        return 0, False
    
    # Check if there's a resolution after the false balance
    has_resolution = any(p.search(text) for p in RESOLUTION_PATTERNS)
    
    return false_balance_count, has_resolution


def count_opinion_laundering(text: str) -> int:
    """Count opinion laundering patterns."""
    return sum(1 for p in OPINION_LAUNDERING if p.search(text))


def count_commitments(text: str) -> int:
    """Count commitment patterns (definitive recommendations/predictions)."""
    return sum(1 for p in COMMITMENT_PATTERNS if p.search(text))


def detect_responsibility_deflection(text: str) -> int:
    """Detect responsibility deflection as conclusion.
    
    Checks if the last paragraph ends with "it depends", "consult expert", etc.
    """
    paragraphs = split_paragraphs(text)
    if not paragraphs:
        return 0
    
    last_para = paragraphs[-1].lower()
    
    deflection_patterns = [
        r"\bit depends\b",
        r"\byour mileage may vary\b",
        r"\bymmv\b",
        r"\bconsult (?:an? )?(?:expert|professional|specialist)\b",
        r"\bseek (?:professional )?(?:advice|guidance)\b",
        r"\bthere(?:'s| is) no (?:one[- ]size[- ]fits[- ]all|silver bullet)\b",
        r"\bresults may vary\b",
    ]
    
    count = sum(1 for pattern in deflection_patterns if re.search(pattern, last_para))
    return count


def analyze_epistemic_cowardice(text: str) -> EpistemicCowardiceAnalysis:
    """Analyze text for epistemic cowardice patterns."""
    
    if len(text.strip()) < 20:
        return EpistemicCowardiceAnalysis(
            hedge_density=0.0,
            hedge_clustering=0,
            false_balance_count=0,
            has_resolution=False,
            opinion_laundering_count=0,
            commitment_count=0,
            responsibility_deflection=0,
            score=0.5,
            verdict="insufficient_data",
        )
    
    hedge_density, hedge_clustering = count_hedge_clustering(text)
    false_balance_count, has_resolution = detect_false_balance(text)
    opinion_laundering_count = count_opinion_laundering(text)
    commitment_count = count_commitments(text)
    responsibility_deflection = detect_responsibility_deflection(text)

    # Detect technical content — technical claims without commitments are cowardly
    words = text.lower().split()
    technical_indicators = sum(1 for w in words if w in {
        "implemented", "added", "updated", "changed", "fixed", "refactored",
        "deployed", "migrated", "configured", "optimized", "improved",
        "caching", "database", "api", "service", "endpoint", "authentication",
        "performance", "scalability", "architecture", "infrastructure",
    })
    is_technical = technical_indicators >= 2

    # Scoring logic — start at 0.5 (neutral)
    score = 0.5

    # Technical content with zero commitments: pull toward cowardly
    # "Implemented X. Performance improved." — no position taken
    if is_technical and commitment_count == 0 and hedge_density < 2.0:
        score -= 0.15  # No position on a technical claim

    # Penalties for cowardice
    if hedge_clustering > 2:
        score -= min((hedge_clustering - 2) * 0.05, 0.25)

    if hedge_density > 3.0:
        score -= min((hedge_density - 3.0) * 0.02, 0.20)

    if false_balance_count > 0 and not has_resolution:
        score -= min(false_balance_count * 0.15, 0.30)

    score -= min(opinion_laundering_count * 0.10, 0.25)

    if responsibility_deflection > 0:
        score -= 0.20

    # Bonuses for commitment
    score += min(commitment_count * 0.08, 0.40)

    if false_balance_count > 0 and has_resolution:
        score += 0.10

    # Clamp to [0, 1]
    score = max(0.0, min(1.0, score))

    # Verdict
    if score >= 0.70:
        verdict = "committed"
    elif score >= 0.50:
        verdict = "balanced"
    elif score >= 0.30:
        verdict = "hedged"
    else:
        verdict = "cowardly"

    return EpistemicCowardiceAnalysis(
        hedge_density=round(hedge_density, 2),
        hedge_clustering=hedge_clustering,
        false_balance_count=false_balance_count,
        has_resolution=has_resolution,
        opinion_laundering_count=opinion_laundering_count,
        commitment_count=commitment_count,
        responsibility_deflection=responsibility_deflection,
        score=round(score, 4),
        verdict=verdict,
    )


def epistemic_cowardice_signal(text: str) -> SignalResult:
    """Generate epistemic cowardice signal for scoring engine."""
    
    analysis = analyze_epistemic_cowardice(text)
    
    # Build detail string
    detail = (
        f"verdict={analysis.verdict} "
        f"hedge_density={analysis.hedge_density}% "
        f"hedge_clustering={analysis.hedge_clustering} "
        f"false_balance={analysis.false_balance_count} "
        f"resolution={analysis.has_resolution} "
        f"opinion_laundering={analysis.opinion_laundering_count} "
        f"commitments={analysis.commitment_count} "
        f"deflection={analysis.responsibility_deflection}"
    )
    
    # Build reason
    if analysis.verdict == "cowardly":
        reason = "Epistemic cowardice detected: hedging without commitment, false balance without resolution, or opinion laundering."
    elif analysis.verdict == "hedged":
        reason = "Excessive hedging detected: many qualifiers without definitive recommendations."
    elif analysis.verdict == "balanced":
        reason = "Balanced reasoning: some hedging but with clear commitments."
    else:
        reason = "Strong commitment: definitive recommendations with minimal hedging."
    
    return SignalResult(
        name="epistemic_cowardice",
        score=analysis.score,
        weight=1.5,  # High weight — this is a novel, hard-to-fake signal
        detail=detail,
        reason=reason,
    )
