import json
from pathlib import Path

from slopguard.scoring import score_text

# Resolve project root: slopguard/evaluate.py is at apps/api/slopguard/evaluate.py
# Project root is 3 levels up: apps/api/slopguard/ -> apps/api/ -> apps/ -> /
_PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent.parent


def _find_samples_path() -> Path:
    """Find the samples JSON file using multiple fallback strategies."""
    # Strategy 1: Relative to project root (monorepo layout)
    candidate = _PROJECT_ROOT / "datasets" / "samples" / "slopguard_samples.json"
    if candidate.is_file():
        return candidate

    # Strategy 2: Relative to API directory (standalone layout)
    candidate = Path(__file__).resolve().parent.parent.parent / "datasets" / "samples" / "slopguard_samples.json"
    if candidate.is_file():
        return candidate

    # Strategy 3: Same directory as evaluate.py
    candidate = Path(__file__).resolve().parent.parent / "datasets" / "samples" / "slopguard_samples.json"
    if candidate.is_file():
        return candidate

    raise FileNotFoundError(
        "Could not find slopguard_samples.json. "
        f"Searched: {_PROJECT_ROOT / 'datasets'}, "
        f"{Path(__file__).resolve().parent.parent.parent / 'datasets'}, "
        f"and local directories."
    )


def evaluate(path: str | None = None) -> dict:
    """Run evaluation against a labeled dataset and return confusion matrix + metrics.

    Accepts either a direct path or None (auto-resolve via _find_samples_path).
    Supports both the internal seed format and HC3-compatible format.
    """
    if path is None:
        path = str(_find_samples_path())

    samples = json.loads(Path(path).read_text(encoding="utf-8"))

    # Normalize HC3 format: HC3 uses "human"|"chatgpt" labels; we map to "reviewed"|"slop"
    normalized = []
    for sample in samples:
        label = sample.get("label", sample.get("human_or_chatgpt", "unknown"))
        if label in ("chatgpt", "slop"):
            label = "slop"
        elif label in ("human", "reviewed"):
            label = "reviewed"
        normalized.append({
            "text": sample.get("text", sample.get("sentence", "")),
            "label": label,
            "domain": sample.get("domain", "general"),
        })

    matrix = {"tp": 0, "tn": 0, "fp": 0, "fn": 0}
    rows = []
    for sample in normalized:
        if not sample["text"]:
            continue
        result = score_text(sample["text"], sample.get("domain", "general"))
        predicted_slop = result.score < 48
        actual_slop = sample["label"] == "slop"
        if predicted_slop and actual_slop:
            matrix["tp"] += 1
        elif predicted_slop and not actual_slop:
            matrix["fp"] += 1
        elif not predicted_slop and actual_slop:
            matrix["fn"] += 1
        else:
            matrix["tn"] += 1
        rows.append({"label": sample["label"], "predicted": result.oversight, "score": result.score})

    total = sum(matrix.values())
    precision = matrix["tp"] / max(matrix["tp"] + matrix["fp"], 1)
    recall = matrix["tp"] / max(matrix["tp"] + matrix["fn"], 1)
    f1 = (2 * precision * recall) / max(precision + recall, 1e-9)
    accuracy = (matrix["tp"] + matrix["tn"]) / max(total, 1)

    # Per-domain breakdown
    by_domain: dict[str, dict] = {}
    for sample, row in zip(normalized, rows):
        if not sample["text"]:
            continue
        domain = sample.get("domain", "general")
        by_domain.setdefault(domain, {"tp": 0, "tn": 0, "fp": 0, "fn": 0})
        actual_slop = sample["label"] == "slop"
        predicted_slop = row["score"] < 48
        if predicted_slop and actual_slop:
            by_domain[domain]["tp"] += 1
        elif predicted_slop and not actual_slop:
            by_domain[domain]["fp"] += 1
        elif not predicted_slop and actual_slop:
            by_domain[domain]["fn"] += 1
        else:
            by_domain[domain]["tn"] += 1

    domain_metrics = {}
    for domain, m in by_domain.items():
        d_precision = m["tp"] / max(m["tp"] + m["fp"], 1)
        d_recall = m["tp"] / max(m["tp"] + m["fn"], 1)
        d_f1 = (2 * d_precision * d_recall) / max(d_precision + d_recall, 1e-9)
        domain_metrics[domain] = {
            "precision": round(d_precision, 3),
            "recall": round(d_recall, 3),
            "f1": round(d_f1, 3),
            "samples": sum(m.values()),
        }

    return {
        "dataset": path,
        "total_samples": total,
        "matrix": matrix,
        "precision": round(precision, 3),
        "recall": round(recall, 3),
        "f1": round(f1, 3),
        "accuracy": round(accuracy, 3),
        "domain_metrics": domain_metrics,
        "rows": rows,
    }


if __name__ == "__main__":
    report = evaluate()
    print(json.dumps(report, indent=2))
