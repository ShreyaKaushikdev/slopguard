"""
Counterfactual Absence Detector

Detects whether the author considered alternatives, failure modes, and tradeoffs.

Real human reasoning contains counterfactuals:
- "I considered X but rejected it because Y"
- "This approach fails if Z"
- "The edge case we're not handling is W"

AI generates the happy path and nothing else.
"""

import re
from slopguard.models import SignalResult


# Rejected alternatives patterns
REJECTED_ALTERNATIVES = [
    r"considered \w+(?:\s+\w+)? but",
    r"instead of \w+(?:\s+\w+)? because",
    r"we tried \w+(?:\s+\w+)? and it (?:failed|didn't work)",
    r"rejected \w+ (?:because|due to|since)",
    r"(?:initially|originally) (?:tried|used|implemented) \w+ but",
    r"explored \w+ (?:but|however)",
    r"evaluated \w+ (?:vs|versus|against) \w+",
    r"compared \w+ (?:to|with|and) \w+"
]

# Explicit failure modes patterns
FAILURE_MODES = [
    r"(?:this|it) (?:breaks|fails|doesn't work) (?:when|if|under)",
    r"edge case[s]?:",
    r"caveat[s]?:",
    r"limitation[s]?:",
    r"(?:doesn't|does not|won't|will not) handle",
    r"(?:known|potential) (?:issue|problem|bug)[s]?",
    r"(?:fails|breaks) (?:when|if|under|with)",
    r"not (?:suitable|appropriate|recommended) (?:for|when|if)",
    r"(?:watch out|be careful|beware) (?:for|of|when)"
]

# Specific conditions patterns
SPECIFIC_CONDITIONS = [
    r"only works (?:if|when|with|for)",
    r"requires (?:that|the|a|an) \w+",
    r"assumes? (?:that|the|a|an)",
    r"precondition[s]?:",
    r"prerequisite[s]?:",
    r"depends on \w+",
    r"must (?:have|be|ensure)",
    r"(?:will|won't) work (?:if|unless|when)"
]

# Tradeoff acknowledgment patterns
TRADEOFF_PATTERNS = [
    r"tradeoff[s]? (?:is|are|between|of)",
    r"(?:sacrifices|trades|exchanges) \w+ for \w+",
    r"(?:costs|downside|drawback)[s]? (?:is|are|of|include)",
    r"(?:benefit|advantage)[s]? (?:at the cost of|at the expense of)",
    r"(?:faster|slower|more|less) \w+ but (?:slower|faster|less|more)",
    r"(?:increases|decreases|improves|reduces) \w+ (?:but|while|at the cost of)"
]

# Generic/vague tradeoff language (penalty)
GENERIC_TRADEOFFS = [
    r"may have (?:performance|scalability|security) implications",
    r"could (?:impact|affect) performance",
    r"might not scale",
    r"has tradeoffs",
    r"depends on (?:your|the) (?:use case|requirements|needs)",
    r"best practice"
]

# Specific numbers/metrics in failure modes (bonus)
SPECIFIC_METRICS = [
    r"\d+(?:k|K|m|M|g|G|b|B|ms|s|%)",  # Numbers with units
    r"(?:exceeds|above|below|under|over) \d+",
    r"(?:more|less) than \d+",
    r"at least \d+",
    r"up to \d+"
]


def count_pattern_matches(text: str, patterns: list[str]) -> int:
    """Count how many patterns match in the text."""
    count = 0
    for pattern in patterns:
        matches = re.findall(pattern, text, re.IGNORECASE)
        count += len(matches)
    return count


def has_specific_metrics_in_failure_modes(text: str) -> bool:
    """Check if failure modes mention specific numbers/metrics."""
    # Find sentences with failure mode language
    sentences = re.split(r'[.!?]+', text)
    
    for sentence in sentences:
        lower = sentence.lower()
        # Check if sentence has failure mode language
        has_failure = any(re.search(pattern, lower) for pattern in FAILURE_MODES)
        # Check if it also has specific metrics
        has_metrics = any(re.search(pattern, sentence) for pattern in SPECIFIC_METRICS)
        
        if has_failure and has_metrics:
            return True
    
    return False


def detect_pure_positive_framing(text: str) -> bool:
    """
    Detect if text is purely positive with no caveats on complex topics.
    Complex topics: architecture, implementation, technical decisions.
    """
    lower = text.lower()
    
    # Indicators of complex technical content
    complex_indicators = [
        "architecture", "implementation", "design", "system", "approach",
        "solution", "algorithm", "database", "api", "service", "cache",
        "performance", "scale", "distributed", "concurrent"
    ]
    
    has_complex_content = any(indicator in lower for indicator in complex_indicators)
    
    if not has_complex_content:
        return False  # Not a complex topic, so pure positive is fine
    
    # Check for any caveat language
    has_caveats = (
        count_pattern_matches(text, FAILURE_MODES) > 0 or
        count_pattern_matches(text, SPECIFIC_CONDITIONS) > 0 or
        count_pattern_matches(text, TRADEOFF_PATTERNS) > 0
    )
    
    return not has_caveats  # Pure positive = complex content with no caveats


def counterfactual_signal(text: str) -> SignalResult:
    """
    Detect presence or absence of counterfactual reasoning.
    
    High score (0.7-1.0) = rich counterfactuals, alternatives, failure modes
    Low score (0.0-0.3) = pure happy path, no alternatives, no failure modes
    """
    
    word_count = len(text.split())
    if word_count < 50:
        return SignalResult(
            name="counterfactual_reasoning",
            score=0.5,
            weight=1.8,
            reason="Text too short to assess counterfactual reasoning."
        )
    
    # Count positive signals
    alternatives_count = count_pattern_matches(text, REJECTED_ALTERNATIVES)
    failure_modes_count = count_pattern_matches(text, FAILURE_MODES)
    conditions_count = count_pattern_matches(text, SPECIFIC_CONDITIONS)
    tradeoffs_count = count_pattern_matches(text, TRADEOFF_PATTERNS)
    
    # Count negative signals
    generic_tradeoffs_count = count_pattern_matches(text, GENERIC_TRADEOFFS)
    pure_positive = detect_pure_positive_framing(text)
    has_specific_metrics = has_specific_metrics_in_failure_modes(text)
    
    # Normalize to per-100-words
    norm_factor = word_count / 100.0
    
    alternatives_score = min(alternatives_count / norm_factor * 0.15, 0.25)
    failure_modes_score = min(failure_modes_count / norm_factor * 0.15, 0.25)
    conditions_score = min(conditions_count / norm_factor * 0.1, 0.15)
    tradeoffs_score = min(tradeoffs_count / norm_factor * 0.1, 0.15)
    
    # Bonuses
    metrics_bonus = 0.1 if has_specific_metrics else 0.0
    
    # Penalties
    generic_penalty = min(generic_tradeoffs_count * 0.05, 0.15)
    pure_positive_penalty = 0.2 if pure_positive else 0.0
    
    # Calculate final score
    score = 0.4  # Base score
    score += alternatives_score + failure_modes_score + conditions_score + tradeoffs_score
    score += metrics_bonus
    score -= generic_penalty + pure_positive_penalty
    score = max(0.0, min(1.0, score))
    
    # Generate reason
    total_counterfactuals = alternatives_count + failure_modes_count + conditions_count + tradeoffs_count
    
    if score < 0.3:
        reason = "No counterfactual reasoning: pure happy path, no alternatives or failure modes mentioned."
        if pure_positive:
            reason += " Complex technical content with zero caveats."
    elif score < 0.5:
        reason = f"Weak counterfactual reasoning: {total_counterfactuals} mention(s) but mostly generic."
        if generic_tradeoffs_count > 0:
            reason += f" {generic_tradeoffs_count} generic tradeoff(s) without specifics."
    elif score < 0.7:
        reason = f"Moderate counterfactual reasoning: {total_counterfactuals} alternatives/caveats mentioned."
    else:
        reason = f"Strong counterfactual reasoning: {alternatives_count} rejected alternatives, "
        reason += f"{failure_modes_count} failure modes, {conditions_count} specific conditions."
        if has_specific_metrics:
            reason += " Includes specific metrics in failure analysis."
    
    return SignalResult(
        name="counterfactual_reasoning",
        score=score,
        weight=1.8,  # Highest weight - this is the most distinctive signal
        reason=reason
    )
