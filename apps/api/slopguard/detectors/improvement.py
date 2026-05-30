"""Before/After Improvement Engine.

When SlopGuard flags a sentence as reasoning theater, this module generates
a concrete prompt for what specific information would make it genuine.

It works by:
1. Identifying what specificity markers are missing
2. Generating targeted questions the author should answer
3. Providing an example rewrite showing what good looks like

This transforms SlopGuard from a judge into a writing coach.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field


@dataclass
class ImprovementSuggestion:
    """A suggestion for improving a flagged sentence."""
    original: str
    issue: str  # What's wrong (e.g., "no measurement", "vague reference")
    questions: list[str]  # Specific questions to answer
    example: str  # Example rewrite
    missing_markers: list[str]  # What specificity markers are absent


# ============================================================================
# Pattern-based improvement templates
# ============================================================================

_IMPROVEMENT_TEMPLATES = {
    "no_measurement": {
        "issue": "No concrete measurement or number provided",
        "questions": [
            "What was the before/after metric?",
            "What tool or method measured this?",
            "What is the specific number (not faster or better)?",
        ],
        "example_template": "Add specific numbers: X changed from {before} to {after} (measured by {tool}).",
    },
    "vague_reference": {
        "issue": "Vague reference without naming the specific entity",
        "questions": [
            "Which specific file, function, or module?",
            "How many various items? Name them.",
            "What specific issues or problems?",
        ],
        "example_template": "Name the entity: Updated {specific_file} to fix {specific_issue}.",
    },
    "pure_adjective": {
        "issue": "Pure adjective without supporting evidence",
        "questions": [
            "What makes it better? Under what conditions?",
            "Better than what? What was the baseline?",
            "Can you show this with a number or example?",
        ],
        "example_template": "Replace adjective with evidence: P95 latency dropped from {X}ms to {Y}ms.",
    },
    "hedged_causal": {
        "issue": "Hedged causal claim (could potentially)",
        "questions": [
            "Did it or did not it? Remove the hedge.",
            "What evidence supports this causal link?",
            "Under what conditions does this hold?",
        ],
        "example_template": "Remove hedge: reduced {X} by {Y} percent in {Z} tests.",
    },
    "fake_specificity": {
        "issue": "Sounds specific but is actually hollow",
        "questions": [
            "Which specific users or scenarios?",
            "What does various aspects actually mean?",
            "Can you name one concrete example?",
        ],
        "example_template": "Replace hollow phrase: {N} users reported {specific_issue} when {specific_condition}.",
    },
    "ai_slop_pattern": {
        "issue": "AI-typical phrasing detected (cliche language)",
        "questions": [
            "What specific thing are you describing? Name it directly.",
            "Can you say this without using cliche language?",
            "What concrete detail would replace this phrase?",
        ],
        "example_template": "Replace cliche: enables {specific_action} for {specific_user}.",
    },
    "no_tool_reference": {
        "issue": "No tool, library, or system mentioned",
        "questions": [
            "What tool, library, or system was involved?",
            "What command, API, or function did you use?",
            "What error message or log output did you see?",
        ],
        "example_template": "Add tool reference: Used {tool} to {action}. Output: {specific_result}.",
    },
    "no_alternative": {
        "issue": "No alternative considered or comparison made",
        "questions": [
            "What other approaches did you consider?",
            "Why this approach over alternatives?",
            "What tradeoffs did you evaluate?",
        ],
        "example_template": "Add comparison: Considered {alternative} but chose {this} because {specific_reason}.",
    },
    "no_failure_mode": {
        "issue": "No failure mode or edge case discussed",
        "questions": [
            "What could go wrong with this change?",
            "What edge cases did you test?",
            "What happens under load or failure?",
        ],
        "example_template": "Add failure mode: Tested {edge_case}. If {condition} fails, system {fallback_behavior}.",
    },
}


def _detect_missing_markers(sentence: str) -> list[str]:
    """Detect what specificity markers are missing from a sentence."""
    missing = []

    has_numbers = bool(re.search(r"\d+(?:\.\d+)?\s*(?:ms|s|px|%|mb|gb|ns|us|requests?|users?|files?)", sentence, re.I))
    if not has_numbers:
        missing.append("numeric_measurement")

    has_files = bool(re.search(r"[a-zA-Z0-9_.-]+\.(?:js|ts|tsx|jsx|py|rb|go|rs|java|c|cpp)", sentence))
    if not has_files:
        missing.append("file_path")

    has_tools = bool(re.search(r"\b(?:profiling|benchmark|test|linter|eslint|prettier|jest|pytest|docker|redis|kafka|postgres)\b", sentence, re.I))
    if not has_tools:
        missing.append("tool_reference")

    has_error_codes = bool(re.search(r"(?:TypeError|ValueError|Error|CVE|PR-\d|GH-\d|HTTP\s*\d{3}|status\s*\d{3})", sentence, re.I))
    if not has_error_codes:
        missing.append("error_code")

    has_named_entity = bool(re.search(r"(?:function|class|method|component|hook|route)\s+['\"]?[A-Z][a-zA-Z]{2,}", sentence, re.I))
    if not has_named_entity:
        missing.append("named_codebase_entity")

    has_alternatives = bool(re.search(r"\b(?:instead of|unlike|alternative|considered|chose)\b", sentence, re.I))
    if not has_alternatives:
        missing.append("comparative_alternative")

    return missing


def _classify_issue(sentence: str) -> str:
    """Classify the primary issue with a sentence."""
    lower = sentence.lower()

    # Hedged causal
    if re.search(r"\b(?:because|since|so|therefore)\s+.*\b(?:may|might|could|can|would|should)\s+(?:potentially|possibly|perhaps|likely)", lower):
        return "hedged_causal"

    # AI slop patterns
    ai_patterns = [
        r"in today's", r"crucial role", r"unlock the power", r"comprehensive",
        r"various aspects", r"game.?changer", r"cutting.?edge", r"delve",
        r"tapestry", r"testament", r"seamless", r"empower", r"harness",
        r"robust solution", r"rich ecosystem",
    ]
    for p in ai_patterns:
        if re.search(p, lower):
            return "ai_slop_pattern"

    # Fake specificity
    if re.search(r"\b(?:some users|certain cases|various issues|multiple scenarios|different conditions)\b", lower):
        return "fake_specificity"

    # Pure adjectives
    if re.search(r"\b(?:better|improved|enhanced|more robust|more efficient|more reliable)\b", lower):
        return "pure_adjective"

    # Vague references
    if re.search(r"\b(?:various|several|multiple|many|some)\s+(?:reasons?|issues?|problems?|changes?|improvements?)\b", lower):
        return "vague_reference"

    # Default: no measurement
    return "no_measurement"


def generate_improvement(sentence: str, domain: str = "general") -> ImprovementSuggestion:
    """Generate an improvement suggestion for a flagged sentence.

    Args:
        sentence: The flagged sentence to improve.
        domain: The domain context (code_review, docs, etc.)

    Returns:
        ImprovementSuggestion with issue, questions, example, and missing markers.
    """
    issue_key = _classify_issue(sentence)
    template = _IMPROVEMENT_TEMPLATES.get(issue_key, _IMPROVEMENT_TEMPLATES["no_measurement"])
    missing = _detect_missing_markers(sentence)

    # Generate a contextual example based on domain
    example = _generate_example(sentence, issue_key, domain)

    return ImprovementSuggestion(
        original=sentence,
        issue=template["issue"],
        questions=template["questions"],
        example=example,
        missing_markers=missing,
    )


def _generate_example(sentence: str, issue_key: str, domain: str) -> str:
    """Generate a domain-specific example rewrite."""
    examples = {
        "code_review": {
            "no_measurement": "Profiling showed auth middleware adding 340ms to every request. P95 latency dropped from 420ms to 85ms after caching.",
            "vague_reference": "Updated billing/retry.ts to cap retries at 3. Stripe was returning duplicate webhooks during deploys.",
            "pure_adjective": "Reduced bundle size from 2.1MB to 340KB by tree-shaking lodash and removing unused moment.js locales.",
            "hedged_causal": "Replaced Node.js streams with pipeline() — eliminated 'stream ended unexpectedly' errors (was 12/day, now 0).",
            "fake_specificity": "3 users reported checkout failures when PayPal returned HTTP 503. Added retry with exponential backoff (max 3, 2s delay).",
            "ai_slop_pattern": "Used Redis to cache session tokens. Cache hit rate: 94%. Session lookup latency: 2ms (was 45ms DB query).",
            "no_tool_reference": "Ran pprof against /api/v2/users — found N+1 query in getUserPermissions(). Added DataLoader, reduced queries from 47 to 3.",
            "no_alternative": "Considered JWT rotation but chose session tokens because we need instant revocation for admin role changes.",
            "no_failure_mode": "If Redis cache misses, falls back to DB query with 5s timeout. Tested with cache pod failure — graceful degradation confirmed.",
        },
        "docs": {
            "no_measurement": "The migration takes 12 minutes on a 50GB database (tested on PostgreSQL 15 with 8 CPU cores).",
            "vague_reference": "Step 3: Run 'npm run db:migrate' — this creates the users_sessions table with 4 indexes.",
            "pure_adjective": "Query latency improved from 120ms (sequential scan) to 8ms (index scan) after adding the composite index.",
            "hedged_causal": "The timeout error occurs when the connection pool is exhausted — we saw this at 50+ concurrent requests.",
            "fake_specificity": "2 users reported the setup script failing on macOS Sonoma. Fixed by replacing 'sed -i' with 'gsed' from Homebrew.",
            "ai_slop_pattern": "Run 'docker compose up' — the API starts on port 8080, the database on 5432. Health check passes in ~8s.",
        },
        "marketplace": {
            "no_measurement": "Battery lasts 14 hours of video playback (tested at 150 nits brightness, WiFi off, with the included earbuds).",
            "vague_reference": "The USB-C port on the left side — it supports USB 3.2 Gen 2 (10 Gbps), not Thunderbolt 4.",
            "pure_adjective": "Screen brightness hits 1,200 nits peak (measured with Sekonic L-478DR). Outdoors visibility is excellent even in direct sunlight.",
            "hedged_causal": "The hinge started creaking after 6 months of daily open/close. The plastic bushing wore down — I replaced it with a metal one.",
            "fake_specificity": "3 of 5 USB-A ports stopped working after the Windows 11 23H2 update. Rolling back to 22H2 fixed it.",
        },
        "academia": {
            "no_measurement": "The model achieved 94.2% accuracy on the test set (n=10,000), compared to 91.7% for the baseline (p < 0.01, paired t-test).",
            "vague_reference": "Table 3 shows the ablation study — removing the attention layer reduces F1 by 4.3 points (from 0.891 to 0.848).",
            "pure_adjective": "The proposed method converges in 47 epochs (vs 120 for SGD), reducing training time from 18h to 6h on a single A100.",
        },
        "content": {
            "no_measurement": "The vulnerability (CVE-2024-1234) affected 2.3 million npm packages. Patch released within 48 hours of disclosure.",
            "vague_reference": "The attack vector was a prototype pollution in lodash.merge() — line 47 of merge.js didn't validate __proto__ keys.",
            "pure_adjective": "The fix reduced the attack surface by 73% — from 14 exploitable endpoints to 4 (measured with Burp Suite Pro).",
        },
        "communications": {
            "no_measurement": "The deploy took 45 minutes (usually 12). Root cause: database migration locked the users table for 38 minutes.",
            "vague_reference": "Alice flagged the issue in #infra at 2:30 PM. The fix (PR #847) was merged at 3:15 PM and deployed at 3:22 PM.",
            "pure_adjective": "Meeting attendance dropped from 12 to 5 after we made camera-optional. Action items increased from 2 to 7 per meeting.",
        },
        "social_news": {
            "no_measurement": "The post got 14,200 upvotes in 6 hours — 83% from accounts created in the last 30 days.",
            "vague_reference": "The screenshot shows the error on line 234 of config.yml — the indentation is 3 spaces instead of 2.",
        },
        "hiring": {
            "no_measurement": "Reduced API latency by 40% (from 200ms to 120ms p95) by implementing Redis caching for user session lookups.",
            "vague_reference": "Led the migration from Jenkins to GitHub Actions — cut CI time from 45min to 12min across 8 microservices.",
        },
    }

    domain_examples = examples.get(domain, examples.get("code_review", {}))
    return domain_examples.get(issue_key, f"Replace vague language with specific measurements, named entities, and concrete examples.")


_VAGUE_VERBS = {
    "improved", "optimized", "enhanced", "fixed", "refactored", "updated",
    "changed", "modified", "adjusted", "streamlined", "boosted", "accelerated",
    "reduced", "increased", "decreased", "resolved", "addressed",
}

_VAGUE_NOUNS = {
    "performance", "issues", "bugs", "problems", "functionality", "experience",
    "quality", "reliability", "stability", "security", "efficiency",
    "various fronts", "multiple fronts", "several areas", "various aspects",
    "better error handling", "better results", "better security", "better design",
}

_VAGUE_QUANTIFIERS = {
    "various", "several", "multiple", "many", "some", "certain", "different",
}


def _is_vague_action(sentence: str) -> tuple[bool, str]:
    """Check if sentence is a vague action statement without evidence.

    Returns (is_vague, issue_type).
    """
    lower = sentence.lower()
    words = set(re.findall(r"\b\w+\b", lower))

    # Check for vague verb + vague noun combo
    has_vague_verb = bool(words & _VAGUE_VERBS)
    has_vague_noun = any(n in lower for n in _VAGUE_NOUNS)
    has_vague_quantifier = bool(words & _VAGUE_QUANTIFIERS)

    # Pure adjective claims
    pure_adj = re.search(
        r"\b(more|better|cleaner|faster|smarter|easier|simpler)\s+"
        r"(?:approach|design|experience|implementation|solution|results|quality)\b",
        lower,
    )

    # Has numbers/evidence?
    has_numbers = bool(re.search(r"\d+(?:\.\d+)?(?:\s*(?:ms|s|%|mb|gb|px|users?|files?))?", lower))

    if has_numbers:
        return False, ""

    if has_vague_verb and has_vague_noun:
        return True, "no_measurement"
    if has_vague_verb and has_vague_quantifier:
        return True, "vague_reference"
    if pure_adj:
        return True, "pure_adjective"

    # Generic improvement without specifics
    if has_vague_verb and len(words) < 12:
        return True, "no_measurement"

    return False, ""


def improve_text(text: str, domain: str = "general") -> dict:
    """Analyze text and generate improvement suggestions for all flagged sentences.

    Args:
        text: The text to analyze.
        domain: The domain context.

    Returns:
        Dict with overall analysis and per-sentence suggestions.
    """
    from slopguard.detectors.specificity import (
        extract_causal_clause,
        score_specificity,
        ai_slop_fingerprint,
    )

    # Split into sentences
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    sentences = [s.strip() for s in sentences if s.strip() and len(s.split()) > 2]

    suggestions = []
    low_score_sentences = []

    for sentence in sentences:
        _, reasoning = extract_causal_clause(sentence)
        if reasoning:
            specificity = score_specificity(reasoning)
            if specificity < 0.5:
                suggestion = generate_improvement(sentence, domain)
                suggestions.append({
                    "sentence": sentence,
                    "specificity": round(specificity, 3),
                    "suggestion": {
                        "issue": suggestion.issue,
                        "questions": suggestion.questions,
                        "example": suggestion.example,
                        "missing_markers": suggestion.missing_markers,
                    },
                })
                low_score_sentences.append(sentence)
        else:
            # Check for AI slop patterns
            fingerprint = ai_slop_fingerprint(sentence)
            if fingerprint["slop_score"] > 0.3:
                suggestion = generate_improvement(sentence, domain)
                suggestions.append({
                    "sentence": sentence,
                    "ai_slop_score": fingerprint["slop_score"],
                    "suggestion": {
                        "issue": suggestion.issue,
                        "questions": suggestion.questions,
                        "example": suggestion.example,
                        "missing_markers": suggestion.missing_markers,
                    },
                })
                low_score_sentences.append(sentence)
            else:
                # Check for vague action statements without evidence
                is_vague, issue_type = _is_vague_action(sentence)
                if is_vague:
                    suggestion = generate_improvement(sentence, domain)
                    suggestions.append({
                        "sentence": sentence,
                        "issue_type": issue_type,
                        "suggestion": {
                            "issue": suggestion.issue,
                            "questions": suggestion.questions,
                            "example": suggestion.example,
                            "missing_markers": suggestion.missing_markers,
                        },
                    })
                    low_score_sentences.append(sentence)

    # Overall assessment
    flagged_ratio = len(low_score_sentences) / max(len(sentences), 1)
    improvement_priority = "high" if flagged_ratio > 0.5 else "medium" if flagged_ratio > 0.25 else "low"

    return {
        "total_sentences": len(sentences),
        "flagged_sentences": len(low_score_sentences),
        "flagged_ratio": round(flagged_ratio, 3),
        "improvement_priority": improvement_priority,
        "suggestions": suggestions,
    }
