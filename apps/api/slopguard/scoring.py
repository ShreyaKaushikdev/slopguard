from slopguard.adapters.baselines import get_relative_score, update_baseline
from slopguard.detectors.domains import batch_clusters, domain_signals
from slopguard.detectors.universal import split_sentences, universal_signals
from slopguard.models import BatchScoreResponse, Domain, RelativeScore, ScoreResponse, SignalResult, TextScoreRequest


def oversight_label(score: float, text: str) -> str:
    if len(text.strip()) < 40:
        return "insufficient"
    if score >= 63:
        return "high"
    if score >= 47:
        return "mixed"
    return "low"


def summarize(score: float, label: str) -> str:
    if label == "insufficient":
        return "Not enough content to judge human oversight reliably."
    if label == "high":
        return "Strong human oversight signals detected."
    if label == "mixed":
        return "Mixed evidence: some useful signals, some slop risk."
    return "Low human oversight signals detected."


def highlights(text: str, signals: list[SignalResult]) -> list[str]:
    if not signals:
        return []
    weak = {signal.name for signal in signals if signal.score < 0.42}
    selected = []
    for sentence in split_sentences(text):
        lower = sentence.lower()
        if "information_density" in weak and len(sentence.split()) > 28:
            selected.append(sentence)
        elif ("why_vs_what" in weak) and any(word in lower for word in ["updated", "improved", "enhanced", "implemented"]):
            selected.append(sentence)
        elif ("concrete_detail" in weak or "specificity" in weak) and not any(char.isdigit() for char in sentence):
            selected.append(sentence)
        if len(selected) >= 3:
            break
    return selected


def score_text(text: str, domain: Domain = "general", metadata: dict | None = None) -> ScoreResponse:
    metadata = metadata or {}

    # Guard: empty or whitespace-only input
    stripped = text.strip()
    if not stripped:
        return ScoreResponse(
            score=0.0,
            oversight="insufficient",
            domain=domain,
            summary="No content provided.",
            reasons=["Input is empty or contains only whitespace."],
            signals=[],
            highlights=[],
            relative=RelativeScore(
                raw=0.0,
                verdict="insufficient_data",
                context="No content to score.",
                baseline_confidence="none",
            ),
        )

    # Guard: single word or very short input (< 3 tokens)
    tokens = stripped.split()
    if len(tokens) < 3:
        return ScoreResponse(
            score=0.0,
            oversight="insufficient",
            domain=domain,
            summary="Insufficient content to score — need at least a few words.",
            reasons=["Text is too short for meaningful signal detection."],
            signals=[],
            highlights=[],
            relative=RelativeScore(
                raw=0.0,
                verdict="insufficient_data",
                context="Need more content to produce a meaningful score.",
                baseline_confidence="none",
            ),
        )

    signals = universal_signals(text, domain) + domain_signals(domain, text, metadata)
    weighted_total = sum(signal.score * signal.weight for signal in signals)
    weight = sum(signal.weight for signal in signals) or 1
    score = round((weighted_total / weight) * 100, 1)
    label = oversight_label(score, text)
    weak_reasons = [signal.reason for signal in signals if signal.score < 0.45]
    strong_reasons = [signal.reason for signal in signals if signal.score >= 0.7]
    reasons = weak_reasons[:4] if weak_reasons else strong_reasons[:4]

    repo_id = metadata.get("repo_id") if metadata else None
    author_id = metadata.get("author_id") if metadata else None

    update_baseline(repo_id=repo_id, author_id=author_id, domain=domain, score=score, signals=[s.model_dump() for s in signals])

    relative_data = get_relative_score(score, repo_id=repo_id, author_id=author_id, domain=domain)

    return ScoreResponse(
        score=score,
        oversight=label,
        domain=domain,
        summary=summarize(score, label),
        reasons=reasons,
        signals=signals,
        highlights=highlights(text, signals),
        relative=RelativeScore(**relative_data),
    )


def score_batch(items: list[TextScoreRequest]) -> BatchScoreResponse:
    scored = [score_text(item.text, item.domain, item.metadata) for item in items]
    clusters = batch_clusters([item.text for item in items])
    return BatchScoreResponse(items=scored, clusters=clusters)

