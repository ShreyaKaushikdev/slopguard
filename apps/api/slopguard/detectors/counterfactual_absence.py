"""Novel Signal 2 — Counterfactual Absence Detector

The insight nobody else has:
When humans actually think about something, they consider what could go wrong,
what alternatives they rejected, and why. AI generates the happy path and nothing else.

Real human reasoning contains counterfactuals. "I considered X but rejected it
because Y." "This approach fails if Z." "The edge case we're not handling is W."
AI almost never generates these unless explicitly prompted, and even when prompted,
the counterfactuals are generic ("this may not scale" rather than "this breaks when
queue depth exceeds 10k messages because Redis pub/sub doesn't buffer").

What it detects:
COUNTERFACTUAL PRESENCE SIGNALS (reward these):
- Rejected alternatives: "considered X but", "instead of Y because",
  "we tried Z and it failed"
- Explicit failure modes: "this breaks when", "edge case:", "caveat:",
  "limitation:", "doesn't handle"
- Specific conditions: "only works if", "requires that", "assumes", "precondition"
- Tradeoff acknowledgment with specifics: not just "tradeoff" but what specifically
  is being traded

COUNTERFACTUAL ABSENCE PENALTY (penalize these):
- Pure positive framing with zero caveats on complex topics
- No alternatives mentioned on architectural decisions
- No failure modes on technical implementations
- "Best practice" claims with no context about when they don't apply

Why it's hard to fake:
To include genuine counterfactuals you need to actually know what could go wrong.
Prompt engineering "add some tradeoffs" produces generic tradeoffs ("may have
performance implications"). Genuine counterfactuals are specific to the exact
implementation being described.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from slopguard.models import SignalResult


# ============================================================================
# Rejected alternatives patterns
# ============================================================================

REJECTED_ALTERNATIVES = [
    re.compile(r"\bconsidered .{5,80} but\b", re.I),
    re.compile(r"\binstead of .{5,80} because\b", re.I),
    re.compile(r"\b(?:we|I) tried .{5,80} (?:and it|but it) (?:failed|didn't work|broke)\b", re.I),
    re.compile(r"\brejected .{5,80} (?:because|due to|since)\b", re.I),
    re.compile(r"\brejected (?:it|that|this|them) because\b", re.I),
    re.compile(r"\b(?:initially|originally|first) (?:tried|used|implemented) .{5,80} but\b", re.I),
    re.compile(r"\breplacing .{5,80} with .{5,80} because\b", re.I),
    re.compile(r"\bswitching from .{5,80} to .{5,80} (?:because|since|as)\b", re.I),
    re.compile(r"\bmigrating (?:away )?from .{5,80} (?:because|due to|since)\b", re.I),
    re.compile(r"\b(?:chose|picked|selected) .{5,80} over .{5,80} (?:because|since)\b", re.I),
    re.compile(r"\balternative(?:s)? (?:considered|evaluated|explored)[:\s]", re.I),
    re.compile(r"\bother options? (?:considered|evaluated|explored)[:\s]", re.I),
    re.compile(r"\bwent with .{3,40} (?:over|instead of|rather than)\b", re.I),
    re.compile(r"\b\w+ over \w+ because\b", re.I),
]

# ============================================================================
# Explicit failure modes patterns
# ============================================================================

FAILURE_MODES = [
    re.compile(r"\bthis (?:breaks|fails|doesn't work|won't work) (?:when|if|under)\b", re.I),
    re.compile(r"\bedge case(?:s)?[:\s]", re.I),
    re.compile(r"\bcaveat(?:s)?[:\s]", re.I),
    re.compile(r"\blimitation(?:s)?[:\s]", re.I),
    re.compile(r"\bknown (?:issue|bug|problem|limitation|risk)(?:s)?[:\s]", re.I),
    re.compile(r"\b(?:doesn't|does not|won't|will not|can't|cannot) (?:handle|support|work with|invalidate|scale)\b", re.I),
    re.compile(r"\b(?:will|would) fail (?:if|when|under)\b", re.I),
    re.compile(r"\b(?:breaks|fails) (?:when|if) .{5,80} (?:exceeds|reaches|drops below)\b", re.I),
    re.compile(r"\bnot (?:thread[- ]safe|reentrant|idempotent)\b", re.I),
    re.compile(r"\b(?:race condition|deadlock|memory leak) (?:when|if|under)\b", re.I),
    re.compile(r"\b(?:assumes|requires|expects) .{5,80} (?:to be|is|are)\b", re.I),
    re.compile(r"\bwhat (?:could|can) go wrong[:\s]", re.I),
    re.compile(r"\bfailure (?:mode|scenario|case)(?:s)?[:\s]", re.I),
    re.compile(r"\b(?:this|that) (?:will|would) (?:break|fail) (?:if|when)\b", re.I),
    # Specific risk/consequence language
    re.compile(r"\b(?:risks?|risk of) (?:showing|causing|creating|introducing)\b", re.I),
    re.compile(r"\b(?:hammer|saturate|exhaust|overwhelm) (?:the )?\w+\b", re.I),  # "hammer the DB"
    re.compile(r"\b(?:cache miss storm|thundering herd|connection exhaustion)\b", re.I),
    re.compile(r"\baccepted (?:that |this )?risk\b", re.I),
    re.compile(r"\bstale (?:data|cache|results?)\b", re.I),
    re.compile(r"\b(?:pool|queue|buffer) (?:exhausted|saturated|full|overflow)\b", re.I),
]

# ============================================================================
# Specific conditions patterns
# ============================================================================

SPECIFIC_CONDITIONS = [
    re.compile(r"\bonly works (?:if|when|under)\b", re.I),
    re.compile(r"\brequires (?:that|the) .{5,80} (?:to be|is|are)\b", re.I),
    re.compile(r"\bassumes .{5,80} (?:is|are|to be)\b", re.I),
    re.compile(r"\bprecondition(?:s)?:\b", re.I),
    re.compile(r"\bpostcondition(?:s)?:\b", re.I),
    re.compile(r"\binvariant(?:s)?:\b", re.I),
    re.compile(r"\b(?:must|need to|have to) (?:ensure|verify|check) (?:that)?\b", re.I),
    re.compile(r"\b(?:if|when) .{5,80} (?:then|,) .{5,80} (?:will|won't|must|can't)\b", re.I),
    re.compile(r"\bdepends on .{5,80} being\b", re.I),
    re.compile(r"\b(?:won't|will not) work (?:if|when|unless)\b", re.I),
]

# ============================================================================
# Tradeoff acknowledgment patterns (with specifics)
# ============================================================================

SPECIFIC_TRADEOFFS = [
    re.compile(r"\btrade[- ]?off[:\s]", re.I),
    re.compile(r"\btrading .{5,80} for .{5,80}\b", re.I),
    re.compile(r"\bsacrificing .{5,80} (?:for|to (?:gain|get))\b", re.I),
    re.compile(r"\b(?:faster|slower|larger|smaller|more|less) .{5,80} but .{5,80}\b", re.I),
    re.compile(r"\b(?:increases|decreases|improves|degrades) .{5,80} (?:at the cost of|but reduces|but increases)\b", re.I),
    re.compile(r"\bthe (?:downside|upside|cost|tradeoff) is .{5,80}\b", re.I),
    re.compile(r"\b(?:pros|benefits):.{10,200}(?:cons|drawbacks|costs):\b", re.I | re.DOTALL),
    re.compile(r"\b(?:advantage|benefit):.{5,80}(?:disadvantage|drawback|cost):\b", re.I),
    # "shorter would X, longer risks Y" — TTL tradeoff pattern
    re.compile(r"\b(?:shorter|lower|smaller|fewer) (?:would|will|could) .{5,60}(?:,|;) (?:longer|higher|larger|more) (?:risks?|would|will)\b", re.I),
    # "X but Y" where X is a positive and Y is a cost
    re.compile(r"\b(?:it's|it is) (?:more|less) .{3,40} but (?:the|it|we)\b", re.I),
    # "verbose but the X is explicit" — explicit tradeoff acknowledgment
    re.compile(r"\bmore verbose but\b", re.I),
    re.compile(r"\bmore (?:complex|complicated|expensive|costly) but\b", re.I),
    # "accepted that risk" — explicit risk acceptance
    re.compile(r"\baccepted (?:that |this )?risk\b", re.I),
    # "X at the cost of Y"
    re.compile(r"\bat the (?:cost|expense|price) of\b", re.I),
]

# ============================================================================
# Generic/hollow counterfactuals (penalize these)
# ============================================================================

GENERIC_COUNTERFACTUALS = [
    re.compile(r"\bmay (?:have|cause) performance (?:implications|issues|problems)\b", re.I),
    re.compile(r"\bcould (?:potentially )?(?:impact|affect) (?:performance|scalability|reliability)\b", re.I),
    re.compile(r"\bmight not scale\b", re.I),
    re.compile(r"\bmay not work in all (?:cases|scenarios|situations)\b", re.I),
    re.compile(r"\b(?:some|certain) (?:edge cases|scenarios|situations) (?:may|might|could)\b", re.I),
    re.compile(r"\bresults may vary\b", re.I),
    re.compile(r"\byour mileage may vary\b", re.I),
    re.compile(r"\bdepending on (?:your|the) (?:use case|requirements|needs)\b", re.I),
]

# ============================================================================
# Best practice claims without context (penalize)
# ============================================================================

BEST_PRACTICE_NO_CONTEXT = [
    re.compile(r"\bbest practice(?:s)?\b(?!.{0,100}(?:when|if|unless|except|but|however))", re.I),
    re.compile(r"\b(?:always|never) (?:use|do|avoid)\b(?!.{0,100}(?:unless|except|when|if))", re.I),
    re.compile(r"\byou should (?:always|never)\b(?!.{0,100}(?:unless|except|when|if))", re.I),
]

# ============================================================================
# Pure positive framing (no caveats on complex topics)
# ============================================================================

COMPLEXITY_INDICATORS = [
    "architecture", "design", "implementation", "algorithm", "optimization",
    "performance", "scalability", "security", "authentication", "authorization",
    "distributed", "concurrent", "parallel", "async", "threading", "locking",
    "caching", "database", "migration", "deployment", "infrastructure",
]

NEGATIVE_WORDS = [
    "but", "however", "although", "caveat", "limitation", "edge case",
    "fails", "breaks", "doesn't", "won't", "can't", "issue", "problem",
    "tradeoff", "cost", "downside", "risk", "concern",
]


# ============================================================================
# Core detection functions
# ============================================================================

@dataclass
class CounterfactualAnalysis:
    """Analysis result for counterfactual absence detection."""
    rejected_alternatives: int
    failure_modes: int
    specific_conditions: int
    specific_tradeoffs: int
    generic_counterfactuals: int
    best_practice_no_context: int
    pure_positive_complex: bool  # Complex topic with zero caveats
    total_counterfactuals: int
    specificity_ratio: float  # Specific vs generic counterfactuals
    score: float  # 0.0 (no counterfactuals) to 1.0 (rich counterfactuals)
    verdict: str


def is_complex_topic(text: str) -> bool:
    """Check if text discusses a complex technical topic."""
    lower = text.lower()
    complexity_count = sum(1 for indicator in COMPLEXITY_INDICATORS if indicator in lower)
    return complexity_count >= 2


def has_negative_framing(text: str) -> bool:
    """Check if text contains any negative/caveat framing."""
    lower = text.lower()
    return any(word in lower for word in NEGATIVE_WORDS)


def analyze_counterfactual_absence(text: str) -> CounterfactualAnalysis:
    """Analyze text for counterfactual presence/absence."""
    
    if len(text.strip()) < 30:
        return CounterfactualAnalysis(
            rejected_alternatives=0,
            failure_modes=0,
            specific_conditions=0,
            specific_tradeoffs=0,
            generic_counterfactuals=0,
            best_practice_no_context=0,
            pure_positive_complex=False,
            total_counterfactuals=0,
            specificity_ratio=0.5,
            score=0.5,
            verdict="insufficient_data",
        )
    
    # Count specific counterfactuals
    rejected_alternatives = sum(1 for p in REJECTED_ALTERNATIVES if p.search(text))
    failure_modes = sum(1 for p in FAILURE_MODES if p.search(text))
    specific_conditions = sum(1 for p in SPECIFIC_CONDITIONS if p.search(text))
    specific_tradeoffs = sum(1 for p in SPECIFIC_TRADEOFFS if p.search(text))
    
    total_specific = rejected_alternatives + failure_modes + specific_conditions + specific_tradeoffs
    
    # Count generic counterfactuals
    generic_counterfactuals = sum(1 for p in GENERIC_COUNTERFACTUALS if p.search(text))
    
    # Count best practice claims without context
    best_practice_no_context = sum(1 for p in BEST_PRACTICE_NO_CONTEXT if p.search(text))
    
    # Check for pure positive framing on complex topics
    is_complex = is_complex_topic(text)
    has_caveats = has_negative_framing(text)
    # Only penalize pure positive framing on longer texts — short summaries legitimately omit tradeoffs
    word_count = len(text.split())
    pure_positive_complex = is_complex and not has_caveats and total_specific == 0 and word_count >= 80
    
    # Total counterfactuals (specific + generic)
    total_counterfactuals = total_specific + generic_counterfactuals
    
    # Specificity ratio
    if total_counterfactuals > 0:
        specificity_ratio = total_specific / total_counterfactuals
    else:
        specificity_ratio = 0.0
    
    # Scoring logic
    score = 0.0
    
    # Bonuses for specific counterfactuals
    # Each rejected alternative: +0.15
    score += min(rejected_alternatives * 0.15, 0.45)
    
    # Each failure mode: +0.12
    score += min(failure_modes * 0.12, 0.36)
    
    # Each specific condition: +0.10
    score += min(specific_conditions * 0.10, 0.30)
    
    # Each specific tradeoff: +0.12
    score += min(specific_tradeoffs * 0.12, 0.36)
    
    # Penalties
    # Generic counterfactuals: -0.08 each (they're better than nothing but not great)
    score -= min(generic_counterfactuals * 0.08, 0.24)
    
    # Best practice without context: -0.10 each
    score -= min(best_practice_no_context * 0.10, 0.30)
    
    # Pure positive framing on complex topic: -0.25
    if pure_positive_complex:
        score -= 0.25
    
    # Bonus for high specificity ratio
    if total_counterfactuals > 0 and specificity_ratio >= 0.75:
        score += 0.15
    
    # Clamp to [0, 1]
    score = max(0.0, min(1.0, score))
    
    # Verdict
    if score >= 0.70:
        verdict = "rich_counterfactuals"
    elif score >= 0.45:
        verdict = "some_counterfactuals"
    elif score >= 0.25:
        verdict = "generic_counterfactuals"
    else:
        verdict = "counterfactual_absence"
    
    return CounterfactualAnalysis(
        rejected_alternatives=rejected_alternatives,
        failure_modes=failure_modes,
        specific_conditions=specific_conditions,
        specific_tradeoffs=specific_tradeoffs,
        generic_counterfactuals=generic_counterfactuals,
        best_practice_no_context=best_practice_no_context,
        pure_positive_complex=pure_positive_complex,
        total_counterfactuals=total_counterfactuals,
        specificity_ratio=round(specificity_ratio, 3),
        score=round(score, 4),
        verdict=verdict,
    )


def counterfactual_absence_signal(text: str) -> SignalResult:
    """Generate counterfactual absence signal for scoring engine."""
    
    analysis = analyze_counterfactual_absence(text)
    
    # Build detail string
    detail = (
        f"verdict={analysis.verdict} "
        f"alternatives={analysis.rejected_alternatives} "
        f"failures={analysis.failure_modes} "
        f"conditions={analysis.specific_conditions} "
        f"tradeoffs={analysis.specific_tradeoffs} "
        f"generic={analysis.generic_counterfactuals} "
        f"best_practice_no_ctx={analysis.best_practice_no_context} "
        f"pure_positive_complex={analysis.pure_positive_complex} "
        f"specificity_ratio={analysis.specificity_ratio}"
    )
    
    # Build reason
    if analysis.verdict == "counterfactual_absence":
        if analysis.pure_positive_complex:
            reason = "Complex topic with zero caveats, failure modes, or alternatives mentioned — pure happy path."
        else:
            reason = "No counterfactual reasoning detected: no alternatives, failure modes, or tradeoffs discussed."
    elif analysis.verdict == "generic_counterfactuals":
        reason = "Generic counterfactuals only: 'may have performance implications' without specifics."
    elif analysis.verdict == "some_counterfactuals":
        reason = "Some counterfactual reasoning present: mentions alternatives, conditions, or tradeoffs."
    else:
        reason = "Rich counterfactual reasoning: specific alternatives rejected, failure modes identified, tradeoffs quantified."
    
    return SignalResult(
        name="counterfactual_absence",
        score=analysis.score,
        weight=1.8,  # Very high weight — this is the strongest novel signal
        detail=detail,
        reason=reason,
    )
