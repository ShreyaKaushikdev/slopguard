#!/usr/bin/env python
"""HC3 Benchmark Integration for SlopGuard.

Downloads the Human ChatGPT Comparison Corpus (HC3) from HuggingFace,
runs SlopGuard evaluation, and publishes results with per-domain breakdowns.

HC3 is a peer-reviewed dataset used in academic NLP research to compare
human-written vs ChatGPT-generated text across multiple domains.

Usage:
    python -m slopguard.evaluate_hc3          # Download + evaluate all domains
    python -m slopguard.evaluate_hc3 --domain reddit    # Evaluate only reddit
    python -m slopguard.evaluate_hc3 --cache  # Use cached dataset if available

Results are saved to datasets/hc3_results.json and published via /evaluation/hc3.
"""

import argparse
import json
import logging
import os
import time
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger(__name__)

# HC3 domains mapped to SlopGuard domains
_HC3_DOMAIN_MAP = {
    "reddit": "social_news",
    "reviews": "marketplace",
    "wiki": "content",
    "academic": "academia",
    "open_qa": "content",
    "closed_qa": "communications",
}

# Subset for fast evaluation (use all domains for full eval)
_FAST_DOMAINS = ["reddit", "reviews"]
_ALL_DOMAINS = ["reddit", "reviews", "wiki", "academic", "open_qa", "closed_qa"]


def download_hc3(domain: str = "all", cache_dir: str = "datasets/hc3_cache") -> list[dict]:
    """Download HC3 dataset from HuggingFace.

    Falls back to manual download if datasets library is not installed.

    Returns list of {"text": str, "human_or_chatgpt": str, "domain": str}.
    """
    Path(cache_dir).mkdir(parents=True, exist_ok=True)

    domains = _ALL_DOMAINS if domain == "all" else [domain]
    all_samples = []

    for d in domains:
        cache_file = Path(cache_dir) / f"{d}.json"
        if cache_file.exists():
            logger.info("Loading cached HC3 data for %s", d)
            samples = json.loads(cache_file.read_text(encoding="utf-8"))
            all_samples.extend(samples)
            continue

        samples = _download_single_domain(d, cache_file)
        if samples:
            all_samples.extend(samples)

    return all_samples


def _download_single_domain(domain: str, cache_file: Path) -> list[dict]:
    """Download a single HC3 domain."""
    logger.info("Downloading HC3 domain: %s", domain)

    # Try HuggingFace datasets library first
    try:
        from datasets import load_dataset

        ds = load_dataset("Hello-SimpleAI/HC3", domain, split="all")
        samples = []
        for item in ds:
            samples.append({
                "text": item.get("question", "") + " " + item.get("answer", "") if item.get("question") else item.get("answer", ""),
                "human_or_chatgpt": item.get("human_or_chatgpt", "unknown"),
                "domain": domain,
            })

        cache_file.write_text(json.dumps(samples, indent=2), encoding="utf-8")
        logger.info("Downloaded %d samples from HC3/%s", len(samples), domain)
        return samples

    except ImportError:
        logger.debug("datasets library not installed, trying manual download")
    except Exception as exc:
        logger.warning("HuggingFace download failed for %s: %s", domain, exc)

    # Manual download from HuggingFace API
    try:
        import urllib.request
        url = f"https://datasets-server.huggingface.co/rows?dataset=Hello-SimpleAI/HC3&config={domain}&split=all&offset=0&length=1000"
        req = urllib.request.Request(url, headers={"User-Agent": "SlopGuard/0.1"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.loads(resp.read().decode())

        samples = []
        for row in data.get("rows", []):
            item = row.get("row", {})
            samples.append({
                "text": item.get("answer", ""),
                "human_or_chatgpt": item.get("human_or_chatgpt", "unknown"),
                "domain": domain,
            })

        if samples:
            cache_file.write_text(json.dumps(samples, indent=2), encoding="utf-8")
            logger.info("Downloaded %d samples from HC3/%s (manual)", len(samples), domain)
            return samples

    except Exception as exc:
        logger.warning("Manual download failed for %s: %s", domain, exc)

    logger.warning("Could not download HC3/%s. Skipping.", domain)
    return []


def evaluate_hc3(samples: list[dict], fast: bool = False) -> dict:
    """Run SlopGuard evaluation on HC3 samples.

    Returns comprehensive metrics with per-domain breakdowns.
    """
    from slopguard.scoring import score_text

    # Filter samples (fast mode uses subset)
    if fast:
        domains = set(_FAST_DOMAINS)
        samples = [s for s in samples if s.get("domain") in domains]

    # Group by domain
    by_domain: dict[str, list[dict]] = {}
    for s in samples:
        d = s.get("domain", "unknown")
        by_domain.setdefault(d, []).append(s)

    # Evaluate each domain
    domain_results = {}
    total_matrix = {"tp": 0, "tn": 0, "fp": 0, "fn": 0}
    total_samples = 0

    for domain, domain_samples in by_domain.items():
        matrix = {"tp": 0, "tn": 0, "fp": 0, "fn": 0}
        scores_human = []
        scores_chatgpt = []
        errors = 0

        for sample in domain_samples:
            text = sample.get("text", "")
            if not text or len(text) < 10:
                continue

            try:
                slopguard_domain = _HC3_DOMAIN_MAP.get(domain, "general")
                result = score_text(text, slopguard_domain)

                # HC3: ChatGPT = slop, Human = reviewed
                is_chatgpt = sample.get("human_or_chatgpt", "").lower() == "chatgpt"
                predicted_slop = result.score < 48

                if predicted_slop and is_chatgpt:
                    matrix["tp"] += 1
                elif predicted_slop and not is_chatgpt:
                    matrix["fp"] += 1
                elif not predicted_slop and is_chatgpt:
                    matrix["fn"] += 1
                else:
                    matrix["tn"] += 1

                if is_chatgpt:
                    scores_chatgpt.append(result.score)
                else:
                    scores_human.append(result.score)

            except Exception as exc:
                logger.debug("Evaluation error for HC3/%s: %s", domain, exc)
                errors += 1

        n = sum(matrix.values())
        precision = matrix["tp"] / max(matrix["tp"] + matrix["fp"], 1)
        recall = matrix["tp"] / max(matrix["tp"] + matrix["fn"], 1)
        f1 = 2 * precision * recall / max(precision + recall, 1e-9)
        accuracy = (matrix["tp"] + matrix["tn"]) / max(n, 1)

        domain_results[domain] = {
            "n_samples": n,
            "accuracy": round(accuracy, 4),
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
            "confusion_matrix": matrix,
            "avg_score_human": round(sum(scores_human) / max(len(scores_human), 1), 2),
            "avg_score_chatgpt": round(sum(scores_chatgpt) / max(len(scores_chatgpt), 1), 2),
            "score_separation": round(
                abs(sum(scores_human) / max(len(scores_human), 1) - sum(scores_chatgpt) / max(len(scores_chatgpt), 1)), 2
            ),
            "errors": errors,
        }

        # Accumulate totals
        for k in total_matrix:
            total_matrix[k] += matrix[k]
        total_samples += n

    # Overall metrics
    n_total = sum(total_matrix.values())
    overall_precision = total_matrix["tp"] / max(total_matrix["tp"] + total_matrix["fp"], 1)
    overall_recall = total_matrix["tp"] / max(total_matrix["tp"] + total_matrix["fn"], 1)
    overall_f1 = 2 * overall_precision * overall_recall / max(overall_precision + overall_recall, 1e-9)
    overall_accuracy = (total_matrix["tp"] + total_matrix["tn"]) / max(n_total, 1)

    return {
        "benchmark": "HC3",
        "dataset": "Hello-SimpleAI/HC3",
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "total_samples": total_samples,
        "domains_evaluated": list(by_domain.keys()),
        "overall": {
            "accuracy": round(overall_accuracy, 4),
            "precision": round(overall_precision, 4),
            "recall": round(overall_recall, 4),
            "f1": round(overall_f1, 4),
            "confusion_matrix": total_matrix,
        },
        "per_domain": domain_results,
        "methodology": {
            "threshold": 48,
            "description": "Score < 48 predicted as slop (ChatGPT). Score >= 48 predicted as human-reviewed.",
            "domains_mapped": _HC3_DOMAIN_MAP,
        },
    }


def main():
    parser = argparse.ArgumentParser(description="Run SlopGuard evaluation on HC3 benchmark")
    parser.add_argument("--domain", default="all", help="HC3 domain to evaluate (or 'all')")
    parser.add_argument("--fast", action="store_true", help="Use fast subset (reddit + reviews only)")
    parser.add_argument("--cache", action="store_true", help="Use cached dataset if available")
    parser.add_argument("--output", default="", help="Output file path (default: datasets/hc3_results.json)")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    print("=" * 60)
    print("SlopGuard HC3 Benchmark Evaluation")
    print("=" * 60)
    print()

    # Download
    print("Downloading HC3 dataset...")
    samples = download_hc3(domain=args.domain)
    if not samples:
        print("ERROR: Could not download HC3 dataset.")
        print()
        print("Options:")
        print("  1. Install HuggingFace datasets: pip install datasets")
        print("  2. Download manually from https://huggingface.co/datasets/Hello-SimpleAI/HC3")
        print("     and place in datasets/hc3_cache/")
        return

    print(f"Loaded {len(samples)} samples from {len(set(s.get('domain', '') for s in samples))} domains")
    print()

    # Evaluate
    print("Running evaluation...")
    start = time.time()
    results = evaluate_hc3(samples, fast=args.fast)
    elapsed = time.time() - start

    # Print results
    print()
    print("=" * 60)
    print("HC3 BENCHMARK RESULTS")
    print("=" * 60)
    print()
    print(f"Total samples: {results['total_samples']}")
    print(f"Domains: {', '.join(results['domains_evaluated'])}")
    print(f"Time: {elapsed:.1f}s")
    print()

    overall = results["overall"]
    print("OVERALL:")
    print(f"  Accuracy:  {overall['accuracy']:.4f}")
    print(f"  Precision: {overall['precision']:.4f}")
    print(f"  Recall:    {overall['recall']:.4f}")
    print(f"  F1:        {overall['f1']:.4f}")
    print()
    print(f"  Confusion Matrix:")
    cm = overall['confusion_matrix']
    print(f"    TP (correctly flagged ChatGPT): {cm['tp']}")
    print(f"    TN (correctly identified human): {cm['tn']}")
    print(f"    FP (false alarm on human):      {cm['fp']}")
    print(f"    FN (missed ChatGPT):            {cm['fn']}")
    print()

    print("PER-DOMAIN:")
    for domain, result in results["per_domain"].items():
        print(f"  {domain}:")
        print(f"    Samples: {result['n_samples']} | F1: {result['f1']:.4f} | Accuracy: {result['accuracy']:.4f}")
        print(f"    Avg human score: {result['avg_score_human']} | Avg ChatGPT score: {result['avg_score_chatgpt']}")
        print(f"    Score separation: {result['score_separation']}")
    print()

    # Save results
    output_path = args.output or str(Path(__file__).resolve().parent.parent.parent.parent / "datasets" / "hc3_results.json")
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    Path(output_path).write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"Results saved to {output_path}")
    print()
    print("To view in API: GET /evaluation/hc3")


if __name__ == "__main__":
    main()
