"""SlopGuard detection engine test suite.

Covers: universal signals, domain adapters, batch clustering,
edge cases, and deterministic output guarantees.
"""

from slopguard.scoring import score_text, score_batch
from slopguard.detectors.universal import (
    universal_signals,
    semantic_uniqueness_proxy,
    human_delta_score,
    information_density,
    why_vs_what,
    template_structure,
)
from slopguard.detectors.domains import (
    code_review_signals,
    docs_signals,
    hiring_signals,
    communications_signals,
    content_signals,
    academia_signals,
    marketplace_signals,
    social_news_signals,
    batch_clusters,
)
from slopguard.models import TextScoreRequest


# ---- Universal signal tests ----


def test_specific_text_scores_higher_than_generic_text():
    generic = "This update improves the system and enhances user experience. It provides a robust solution for various aspects."
    specific = "We changed auth/session.ts to rotate refresh tokens every 15 minutes because replay risk increased after the mobile login rollout."

    assert score_text(specific, "code_review").score > score_text(generic, "code_review").score


def test_short_text_is_insufficient():
    result = score_text("Looks good.", "code_review")
    assert result.oversight == "insufficient"


def test_marketplace_specificity_rewards_product_details():
    generic = "Amazing product. Great quality. Highly recommend it to everyone."
    specific = "The 5000 mAh battery lasted 9 hours, but the USB-C port got warm after the third charge."

    assert score_text(specific, "marketplace").score > score_text(generic, "marketplace").score


def test_information_density_rewards_dense_text():
    dense = "Changed billing/retry.ts to cap retries at 3 because Stripe returned duplicate webhook delivery during deploys. Added a 10 minute idempotency window."
    sparse = "Updated the implementation and improved the system. This enhances the user experience and provides a robust solution for the application."
    dense_result = information_density(dense)
    sparse_result = information_density(sparse)
    assert dense_result.score > sparse_result.score


def test_why_vs_what_detects_reasoning():
    reasoned = "We chose to cap retries at 3 because exceeding that caused duplicate charges. The tradeoff is slower recovery, but the risk of double-billing outweighed speed."
    action_only = "Updated the retry logic. Fixed the billing module. Improved error handling. Refactored the payment flow."
    reasoned_result = why_vs_what(reasoned)
    action_result = why_vs_what(action_only)
    assert reasoned_result.score > action_result.score


def test_template_structure_detects_uniformity():
    uniform = "This tool is amazing. This tool is powerful. This tool is innovative. This tool is essential. This tool is transformative."
    varied = "The USB-C connector is loose on mine. Battery lasts about 6 hours. I wouldn't pay full price, but it works fine for meetings."
    uniform_result = template_structure(uniform)
    varied_result = template_structure(varied)
    # Varied text should score higher (less templated)
    assert varied_result.score >= uniform_result.score or abs(varied_result.score - uniform_result.score) < 0.15


def test_semantic_uniqueness_is_deterministic():
    text = "In today's digital landscape, it is important to note that robust solutions play a crucial role in enhancing user experience."
    result1 = semantic_uniqueness_proxy(text)
    result2 = semantic_uniqueness_proxy(text)
    assert result1.score == result2.score, f"Non-deterministic: {result1.score} != {result2.score}"


def test_human_delta_detects_editing_signals():
    edited = "Actually, wait — I originally said 3 retries but I think 5 is better. Correction: the timeout was 10s not 15s. However, we might need to revisit this."
    pristine = "The system has been updated and improved. This change enhances the user experience and provides a comprehensive solution."
    edited_result = human_delta_score(edited)
    pristine_result = human_delta_score(pristine)
    assert edited_result.score > pristine_result.score


def test_universal_signals_returns_ten_signals():
    """Test that universal_signals returns all 10 signals including 3 novel ones."""
    text = "This is a test sentence with enough words to properly analyze the content for signal detection purposes."
    signals = universal_signals(text)
    assert len(signals) == 10
    
    # Verify the three novel signals are present
    signal_names = {s.name for s in signals}
    assert "epistemic_cowardice" in signal_names
    assert "counterfactual_absence" in signal_names
    assert "vocabulary_novelty" in signal_names


# ---- Domain adapter tests ----


def test_code_review_diff_divergence():
    description = "Changed the retry logic to cap at 3 because of Stripe webhook duplication."
    diff = "+ retryCount = Math.min(retryCount + 1, 3)\n+ idempotencyWindowMinutes = 10"
    signals = code_review_signals(description, diff)
    names = [s.name for s in signals]
    assert "pr_diff_divergence" in names


def test_docs_detects_patterns():
    doc = "# Setup\n\nThis guide explains setup. Setup is important. The setup process is key.\n# Configuration\n\nConfiguration is vital."
    signals = docs_signals(doc)
    names = [s.name for s in signals]
    assert "heading_to_content_ratio" in names
    assert "circular_explanation_graph" in names


def test_hiring_detects_template_applications():
    template = "I am excited to apply for this role at your company. My passion and dedication make me a great fit. I am confident I can contribute to your team."
    specific = "At PayFlow I reduced failed invoice retries by 22% by adding queue backoff. Your billing infrastructure role maps directly to that work."
    template_score = score_text(template, "hiring").score
    specific_score = score_text(specific, "hiring").score
    assert specific_score > template_score


def test_communications_rewards_action_items():
    actionable = "Decision: ship the smaller importer on Friday. Owner is Riya. Blocker is the CSV date parser; Amit will patch it by 4 PM."
    vague = "I wanted to circle back and provide a comprehensive update regarding the ongoing initiative. We are continuing to make progress."
    signals_actionable = communications_signals(actionable)
    signals_vague = communications_signals(vague)
    action_scores = [s.score for s in signals_actionable]
    vague_scores = [s.score for s in signals_vague]
    assert sum(action_scores) / len(action_scores) > sum(vague_scores) / len(vague_scores)


def test_content_detects_unsupported_claims():
    unsupported = "Research shows that this is the best approach. Studies prove that it always works. Experts agree this is essential for success."
    supported = "According to a 2024 Gartner report (source: gartner.com/doc/1234), 78% of enterprises adopted this pattern. The benchmark data showed 3x improvement."
    signals_unsupported = content_signals(unsupported)
    signals_supported = content_signals(supported)
    claim_unsupported = next(s for s in signals_unsupported if s.name == "claim_specificity")
    claim_supported = next(s for s in signals_supported if s.name == "claim_specificity")
    assert claim_supported.score > claim_unsupported.score


def test_marketplace_rewards_product_details():
    generic = "Amazing product! Great quality. Highly recommend. Five stars!"
    specific = "The XL black hoodie shrank 2 cm after cold wash, but the zipper stayed smooth and sleeve cuffs didn't pill after three weeks."
    signals_generic = marketplace_signals(generic)
    signals_specific = marketplace_signals(specific)
    spec_avg = sum(s.score for s in signals_specific) / len(signals_specific)
    gen_avg = sum(s.score for s in signals_generic) / len(signals_generic)
    assert spec_avg > gen_avg


def test_social_news_detects_rage_bait():
    rage = "You won't believe what was exposed today! This SHOCKING revelation destroyed everything they thought was true. Share everywhere before they delete this!"
    sourced = "According to a Reuters report from May 2024, the committee published their findings showing a 12% decline. The spokesperson declined to comment."
    signals_rage = social_news_signals(rage)
    signals_sourced = social_news_signals(sourced)
    rage_avg = sum(s.score for s in signals_rage) / len(signals_rage)
    sourced_avg = sum(s.score for s in signals_sourced) / len(signals_sourced)
    assert sourced_avg > rage_avg


def test_academia_signals_exist():
    text = "This paper presents a novel method (Smith et al., 2023). Our results show p-value < 0.05 with confidence interval [0.3, 0.7]. Limitations include small sample size."
    signals = academia_signals(text)
    assert len(signals) >= 3
    names = [s.name for s in signals]
    assert "academic_grounding" in names


# ---- Batch clustering tests ----


def test_batch_clusters_identical_items():
    texts = [
        "Amazing product. Great quality. Highly recommend.",
        "Amazing product. Great quality. Highly recommend.",
        "The battery lasted 9 hours and the screen is bright at 500 nits.",
    ]
    clusters = batch_clusters(texts)
    assert len(clusters) > 0
    # Items 0 and 1 should be clustered together
    found = False
    for cluster in clusters:
        if 0 in cluster["item_indexes"] and 1 in cluster["item_indexes"]:
            found = True
            break
    assert found, "Identical items were not clustered together"


def test_batch_clusters_unique_items():
    texts = [
        "Changed auth/session.ts to rotate tokens every 15 minutes because of replay risk.",
        "The XL hoodie shrank 2 cm after first wash but zipper stayed smooth.",
        "Decision: ship importer Friday. Owner: Riya. Blocker: CSV parser. Amit patches by 4 PM.",
    ]
    clusters = batch_clusters(texts)
    # All items are unique, so there should be few or no clusters
    structural_clusters = [c for c in clusters if c["type"] == "structural_template"]
    assert len(structural_clusters) == 0


# ---- Edge case tests ----


def test_very_short_text():
    result = score_text("OK", "general")
    assert result.oversight == "insufficient"
    assert result.score >= 0


def test_unicode_text():
    result = score_text(
        "この更新はシステムを改善し、ユーザーエクスペリエンスを向上させます。堅牢なソリューションを提供します。",
        "general",
    )
    assert result.score >= 0
    assert result.oversight in ("high", "mixed", "low", "insufficient")


def test_very_long_text_doesnt_crash():
    text = "This sentence is about testing long content. " * 500
    result = score_text(text, "content")
    assert result.score >= 0
    assert len(result.signals) > 0


def test_empty_domain_returns_signals():
    result = score_text(
        "This is a general text that should be scored with universal signals only for testing purposes across the system.",
        "general",
    )
    assert len(result.signals) > 0


# ---- Integration tests ----


def test_score_text_returns_valid_response():
    result = score_text(
        "Changed billing/retry.ts to cap retries at 3 because Stripe duplicate webhooks during deploys.",
        "code_review",
    )
    assert 0 <= result.score <= 100
    assert result.oversight in ("high", "mixed", "low", "insufficient")
    assert result.domain == "code_review"
    assert len(result.signals) > 0
    assert result.summary != ""


def test_all_domains_produce_signals():
    text = "This is a test text with enough content to generate signals across different domain adapters for verification purposes."
    for domain in ["code_review", "docs", "hiring", "communications", "content", "academia", "marketplace", "social_news", "general"]:
        result = score_text(text, domain)
        assert len(result.signals) > 0, f"Domain {domain} produced no signals"


def test_score_consistency():
    text = "Updated the billing module and improved error handling. This enhances reliability and provides a robust solution."
    result1 = score_text(text, "code_review")
    result2 = score_text(text, "code_review")
    assert result1.score == result2.score, "Same input must produce same output"
    assert result1.oversight == result2.oversight


def test_score_batch_clusters_and_scores():
    items = [
        TextScoreRequest(text="Amazing product. Great quality. Highly recommend.", domain="marketplace"),
        TextScoreRequest(text="Amazing product. Great quality. Highly recommend.", domain="marketplace"),
        TextScoreRequest(text="Battery lasted 9 hours. USB-C port warm after third charge.", domain="marketplace"),
    ]
    result = score_batch(items)
    assert len(result.items) == 3
    assert isinstance(result.clusters, list)


# ---- Adversarial Slop Detection tests ----


def test_specificity_high_for_falsifiable_reasoning():
    """Specific, falsifiable reasoning should score high."""
    from slopguard.detectors.specificity import score_specificity

    reasoning = "profiling showed auth middleware adding 340ms to every request"
    score = score_specificity(reasoning)
    assert score >= 0.6, f"Expected high specificity, got {score}"


def test_specificity_low_for_unfalsifiable_reasoning():
    """Vague, unfalsifiable reasoning should score low."""
    from slopguard.detectors.specificity import score_specificity

    reasoning = "it was slow"
    score = score_specificity(reasoning)
    assert score <= 0.3, f"Expected low specificity, got {score}"


def test_specificity_medium_for_comparative():
    """Comparative language with implicit measurement should score medium."""
    from slopguard.detectors.specificity import score_specificity

    reasoning = "significantly faster than the previous approach"
    score = score_specificity(reasoning)
    assert 0.3 <= score <= 0.7, f"Expected medium specificity, got {score}"


def test_specificity_detects_file_paths():
    """File paths should count as high specificity."""
    from slopguard.detectors.specificity import score_specificity

    reasoning = "changed auth/middleware.js to fix the timeout issue"
    score = score_specificity(reasoning)
    assert score >= 0.5, f"Expected medium-high specificity for file path, got {score}"


def test_specificity_detects_error_codes():
    """Error codes should count as high specificity."""
    from slopguard.detectors.specificity import score_specificity

    reasoning = "fixed TypeError: cannot read property of undefined on line 47"
    score = score_specificity(reasoning)
    assert score >= 0.5, f"Expected medium-high specificity for error code, got {score}"


def test_specificity_detects_tool_references():
    """Tool/profiler references should count as high specificity."""
    from slopguard.detectors.specificity import score_specificity

    reasoning = "bundle analysis showed moment adding 67kb to the main chunk"
    score = score_specificity(reasoning)
    assert score >= 0.5, f"Expected medium-high specificity for tool reference, got {score}"


def test_blend_confidence_penalizes_unfalsifiable():
    """Blending should reduce WHY credit for unfalsifiable reasoning."""
    from slopguard.detectors.specificity import blend_confidence

    # High WHY confidence, zero specificity → 60% penalty
    blended = blend_confidence(0.9, 0.0)
    assert abs(blended - 0.36) < 0.01, f"Expected ~0.36, got {blended}"
    assert blended < 0.9


def test_blend_confidence_preserves_specific():
    """Blending should preserve WHY credit for specific reasoning."""
    from slopguard.detectors.specificity import blend_confidence

    # High WHY confidence, high specificity → minimal penalty
    blended = blend_confidence(0.9, 1.0)
    assert blended == 0.9  # No penalty


def test_specific_text_scores_higher_than_prompt_engineered():
    """Genuine specific reasoning should score higher than prompt-engineered AI slop."""
    # Prompt-engineered: has causal language but zero specifics
    prompt_engineered = (
        "I chose this approach because it aligns better with our architectural "
        "principles and provides improved maintainability going forward."
    )
    # Genuine: has causal language AND specific, falsifiable details
    genuine = (
        "Switched from moment.js to date-fns because our bundle analysis showed "
        "moment adding 67kb to the main chunk — date-fns tree-shakes to 3kb."
    )
    genuine_score = score_text(genuine, "code_review").score
    engineered_score = score_text(prompt_engineered, "code_review").score
    assert genuine_score > engineered_score, (
        f"Genuine ({genuine_score}) should score higher than prompt-engineered ({engineered_score})"
    )


def test_why_vs_what_returns_specificity_fields():
    """WHY/WHAT signal should return specificity_score, reasoning_quality, flagged_claims, strong_claims."""
    result = why_vs_what(
        "We capped retries at 3 because profiling showed duplicate charges costing $200/day."
    )
    assert result.specificity_score is not None
    assert result.reasoning_quality in ("specific", "mixed", "qualitative", "unfalsifiable", "insufficient_data", "no_reasoning_detected")
    assert isinstance(result.flagged_claims, list)
    assert isinstance(result.strong_claims, list)


def test_unfalsifiable_reasoning_is_flagged():
    """Unfalsifiable reasoning should appear in flagged_claims."""
    result = why_vs_what(
        "Updated the code because it was slow and messy."
    )
    # With unfalsifiable reasoning, we expect at least 1 flagged claim
    assert len(result.flagged_claims) >= 1
    assert result.flagged_claims[0]["verdict"] in ("unfalsifiable_reasoning", "generic_reasoning")


def test_domain_calibration_affects_threshold():
    """Different domains should have different specificity thresholds."""
    from slopguard.detectors.specificity import DOMAIN_THRESHOLDS

    assert DOMAIN_THRESHOLDS["academia"]["high_bar"] > DOMAIN_THRESHOLDS["communications"]["high_bar"]
    assert DOMAIN_THRESHOLDS["code_review"]["high_bar"] >= 0.6
    assert DOMAIN_THRESHOLDS["communications"]["high_bar"] <= 0.3


# ---- Task 1: Real-world scenario tests ----


def test_vague_pr_scores_low():
    """Vague PR description should score LOW and be flagged as unfalsifiable."""
    result = score_text("Updated authentication flow to fix security issues", "code_review")
    assert result.oversight in ("low", "insufficient"), f"Expected low/insufficient, got {result.oversight}"
    assert result.score < 50, f"Expected score < 50, got {result.score}"


def test_specific_pr_scores_higher_than_vague():
    """Specific JWT PR should score significantly higher than vague PR."""
    vague = score_text("Updated authentication flow to fix security issues", "code_review")
    specific = score_text(
        "Fixed JWT secret exposure in auth/middleware.js \u2014 previous implementation "
        "logged the full token on line 47, appearing in CloudWatch logs accessible to the "
        "ops team. Rotated all affected secrets, added log sanitization, updated tests.",
        "code_review",
    )
    assert specific.score > vague.score, f"Specific ({specific.score}) should beat vague ({vague.score})"
    # Strong claims should be detected
    why_signal = next((s for s in specific.signals if s.name == "why_vs_what"), None)
    assert why_signal is not None
    assert len(why_signal.strong_claims) >= 1, "Expected at least 1 strong claim"


def test_empty_string_returns_graceful_error():
    """Empty string should return graceful insufficient response, not crash."""
    result = score_text("", "general")
    assert result.oversight == "insufficient"
    assert result.score == 0.0
    assert result.relative.verdict == "insufficient_data"
    assert len(result.signals) == 0


def test_single_word_returns_insufficient():
    """Single word should return insufficient_data, not a computed score."""
    result = score_text("Hello", "general")
    assert result.oversight == "insufficient"
    assert result.score == 0.0
    assert result.relative.verdict == "insufficient_data"


def test_long_document_completes_quickly():
    """5000-word document should complete without timeout."""
    import time
    long_text = (
        "This is a detailed technical analysis of the authentication system. "
        "The system uses JWT tokens with RS256 signing. The token expiry is set to 15 minutes. "
        "The refresh token window is 7 days. We measured the auth latency at P95=45ms. "
    ) * 100
    start = time.time()
    result = score_text(long_text, "code_review")
    elapsed = time.time() - start
    assert elapsed < 10.0, f"Took too long: {elapsed:.2f}s"
    assert result.score >= 0
    assert result.oversight in ("high", "mixed", "low", "insufficient")


# ---- Task 2: Baseline cold start ----


def test_baseline_cold_start_returns_null_not_zero():
    """First score for a repo should return null repo_mean, not 0."""
    from slopguard.adapters.baselines import clear_all, get_relative_score

    clear_all()
    relative = get_relative_score(55.0, repo_id="test-repo-cold-start", domain="code_review")
    assert relative["repo_mean"] is None, f"Expected None, got {relative['repo_mean']}"
    assert relative["author_mean"] is None, f"Expected None, got {relative['author_mean']}"
    assert relative["baseline_confidence"] == "none"


# ---- Task 3: Ticker empty state ----


def test_ticker_empty_state_returns_warming_up():
    """Fresh ticker with no scoring history should return warming_up state."""
    from slopguard.adapters.baselines import clear_all
    from slopguard.adapters.ticker import get_ticker_snapshot

    clear_all()
    snapshot = get_ticker_snapshot()
    assert snapshot.get("state") == "warming_up", f"Expected warming_up, got {snapshot}"
    assert snapshot.get("total_scored") == 0
    assert "message" in snapshot


# ---- Task 4: Improvement engine quality ----


def test_improvement_engine_returns_specific_questions():
    """Improvement suggestions must be specific questions, not generic advice."""
    from slopguard.detectors.improvement import improve_text

    result = improve_text("I updated the function because it was slow and needed improvement", "code_review")
    assert result["flagged_sentences"] >= 1, "Expected at least 1 flagged sentence"
    suggestion = result["suggestions"][0]["suggestion"]
    # Questions should be specific (contain measurement/tool/comparison language)
    questions = suggestion["questions"]
    assert len(questions) >= 1
    # At least one question should ask for a specific measurement or comparison
    specific_keywords = ["metric", "measurement", "number", "before", "after", "tool", "method", "how", "which", "what"]
    has_specific = any(
        any(kw in q.lower() for kw in specific_keywords)
        for q in questions
    )
    assert has_specific, f"Questions are too generic: {questions}"
