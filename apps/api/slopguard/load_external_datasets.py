#!/usr/bin/env python
"""Load HC3 and RAID benchmark datasets and convert to SlopGuard format.

Usage:
    python -m slopguard.load_external_datasets --hc3
    python -m slopguard.load_external_datasets --raid
    python -m slopguard.load_external_datasets --hc3 --raid --evaluate
"""

from __future__ import annotations

import argparse
import json
import random
import time
from pathlib import Path

random.seed(42)

BASE = Path(__file__).resolve().parent.parent.parent.parent
SAMPLES_DIR = BASE / "datasets" / "samples"
SAMPLES_DIR.mkdir(parents=True, exist_ok=True)


# ---------------------------------------------------------------------------
# HC3 — Human ChatGPT Comparison Corpus
# ---------------------------------------------------------------------------

HC3_DOMAIN_MAP = {
    "reddit":      "social_news",
    "wiki":        "content",
    "medicine":    "academia",
    "finance":     "content",
    "open_qa":     "content",
    "closed_qa":   "communications",
    "all":         "content",
}


def load_hc3(subset: str = "all", max_per_label: int = 2000) -> list[dict]:
    """Download HC3 and convert to SlopGuard format.

    Returns list of {"text", "label", "domain", "source"}.
    """
    try:
        from datasets import load_dataset
    except ImportError:
        print("Run: pip install datasets")
        return []

    print(f"Downloading HC3/{subset} from HuggingFace...")

    # HC3 no longer supports loading scripts — use data_files directly
    subset_files = {
        "reddit":   "data/reddit_eli5.jsonl",
        "wiki":     "data/wiki_csai.jsonl",
        "medicine": "data/medicine.jsonl",
        "finance":  "data/finance.jsonl",
        "open_qa":  "data/open_qa.jsonl",
        "all":      None,  # load all subsets
    }

    try:
        if subset == "all":
            # Load each subset individually and combine
            all_samples = []
            for sub in ["reddit", "wiki", "medicine", "finance", "open_qa"]:
                sub_samples = load_hc3(sub, max_per_label=max_per_label // 5)
                all_samples.extend(sub_samples)
            return all_samples

        # Try loading via HuggingFace datasets API (newer format)
        try:
            ds = load_dataset("Hello-SimpleAI/HC3", subset)
        except Exception:
            # Fallback: load via HTTP directly
            return _load_hc3_http(subset, max_per_label)

        split = ds.get("train") or ds.get("test") or list(ds.values())[0]
        domain = HC3_DOMAIN_MAP.get(subset, "content")

        samples: list[dict] = []
        human_count = 0
        chatgpt_count = 0

        for item in split:
            for answer in (item.get("human_answers") or []):
                if isinstance(answer, str) and len(answer.split()) >= 30:
                    if human_count < max_per_label:
                        samples.append({
                            "text": answer[:1500],
                            "label": "reviewed",
                            "domain": domain,
                            "source": f"hc3_{subset}",
                        })
                        human_count += 1

            for answer in (item.get("chatgpt_answers") or []):
                if isinstance(answer, str) and len(answer.split()) >= 30:
                    if chatgpt_count < max_per_label:
                        samples.append({
                            "text": answer[:1500],
                            "label": "slop",
                            "domain": domain,
                            "source": f"hc3_{subset}",
                        })
                        chatgpt_count += 1

        print(f"  HC3/{subset}: {human_count} human + {chatgpt_count} ChatGPT = {len(samples)} total")
        return samples

    except Exception as e:
        print(f"  HC3/{subset} HF failed ({e}), trying HTTP fallback...")
        return _load_hc3_http(subset, max_per_label)


def _load_hc3_http(subset: str, max_per_label: int) -> list[dict]:
    """Load HC3 via HuggingFace datasets-server API (no script needed)."""
    import urllib.request

    domain = HC3_DOMAIN_MAP.get(subset, "content")
    url = (
        f"https://datasets-server.huggingface.co/rows"
        f"?dataset=Hello-SimpleAI%2FHC3&config={subset}&split=train"
        f"&offset=0&length=1000"
    )

    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SlopGuard/0.2"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = json.loads(r.read().decode())
    except Exception as e:
        print(f"  HTTP fallback also failed: {e}")
        return []

    samples: list[dict] = []
    human_count = 0
    chatgpt_count = 0

    for row in data.get("rows", []):
        item = row.get("row", {})

        for answer in (item.get("human_answers") or []):
            if isinstance(answer, str) and len(answer.split()) >= 30:
                if human_count < max_per_label:
                    samples.append({
                        "text": answer[:1500],
                        "label": "reviewed",
                        "domain": domain,
                        "source": f"hc3_{subset}",
                    })
                    human_count += 1

        for answer in (item.get("chatgpt_answers") or []):
            if isinstance(answer, str) and len(answer.split()) >= 30:
                if chatgpt_count < max_per_label:
                    samples.append({
                        "text": answer[:1500],
                        "label": "slop",
                        "domain": domain,
                        "source": f"hc3_{subset}",
                    })
                    chatgpt_count += 1

    print(f"  HC3/{subset} (HTTP): {human_count} human + {chatgpt_count} ChatGPT = {len(samples)} total")
    return samples


# ---------------------------------------------------------------------------
# RAID — Rigorous AI Detection benchmark
# ---------------------------------------------------------------------------

RAID_DOMAIN_MAP = {
    "news":        "content",
    "reddit":      "social_news",
    "recipes":     "content",
    "abstracts":   "academia",
    "reviews":     "marketplace",
    "wiki":        "content",
    "books":       "content",
    "poetry":      "content",
}


def load_raid(max_samples: int = 3000) -> list[dict]:
    """Download RAID benchmark and convert to SlopGuard format.

    RAID is the most rigorous AI detection benchmark — peer-reviewed,
    multiple generators, adversarial attacks included.
    """
    try:
        from datasets import load_dataset
    except ImportError:
        print("Run: pip install datasets")
        return []

    print("Downloading RAID benchmark from HuggingFace...")
    try:
        ds = load_dataset("liamdugan/raid", split="train", trust_remote_code=True)
    except Exception as e:
        print(f"RAID download failed: {e}")
        # Try alternate split name
        try:
            ds = load_dataset("liamdugan/raid", trust_remote_code=True)
            ds = ds.get("train") or list(ds.values())[0]
        except Exception as e2:
            print(f"RAID alternate also failed: {e2}")
            return []

    samples: list[dict] = []
    seen: set[str] = set()

    for item in ds:
        text = (item.get("generation") or item.get("text") or "").strip()
        raw_label = (item.get("label") or item.get("model") or "").lower()
        raw_domain = (item.get("domain") or "").lower()

        if not text or len(text.split()) < 20:
            continue

        key = text[:80]
        if key in seen:
            continue
        seen.add(key)

        # Map label
        if raw_label in ("human", "reviewed"):
            label = "reviewed"
        elif raw_label in ("ai", "chatgpt", "gpt", "gpt-4", "gpt-3.5", "claude",
                           "llama", "mistral", "cohere", "davinci"):
            label = "slop"
        else:
            continue  # skip unknown labels

        domain = RAID_DOMAIN_MAP.get(raw_domain, "content")

        samples.append({
            "text": text[:1500],
            "label": label,
            "domain": domain,
            "source": f"raid_{raw_domain}",
        })

        if len(samples) >= max_samples:
            break

    human = sum(1 for s in samples if s["label"] == "reviewed")
    ai = sum(1 for s in samples if s["label"] == "slop")
    print(f"  RAID: {human} human + {ai} AI = {len(samples)} total")
    return samples


# ---------------------------------------------------------------------------
# Merge with existing dataset
# ---------------------------------------------------------------------------

def merge_and_save(new_samples: list[dict], output_name: str) -> Path:
    """Merge new samples with existing merged_dataset.json and save."""
    merged_path = SAMPLES_DIR / "merged_dataset.json"
    existing: list[dict] = []

    if merged_path.exists():
        existing = json.loads(merged_path.read_text(encoding="utf-8"))
        print(f"Existing merged dataset: {len(existing)} samples")

    # Deduplicate by text prefix
    seen: set[str] = {s["text"][:80] for s in existing}
    added = 0
    for s in new_samples:
        key = s["text"][:80]
        if key not in seen:
            existing.append(s)
            seen.add(key)
            added += 1

    print(f"Added {added} new samples → total {len(existing)}")

    # Save new combined file
    out_path = SAMPLES_DIR / output_name
    out_path.write_text(json.dumps(existing, indent=2), encoding="utf-8")
    print(f"Saved → {out_path}")
    return out_path


# ---------------------------------------------------------------------------
# Evaluation
# ---------------------------------------------------------------------------

def evaluate_dataset(path: Path, label: str = "") -> dict:
    """Run SlopGuard evaluation on a dataset file."""
    from slopguard.scoring import score_text
    from collections import defaultdict

    samples = json.loads(path.read_text(encoding="utf-8"))
    print(f"\nEvaluating {label or path.name} ({len(samples)} samples)...")

    THRESHOLD = 48
    matrix = {"tp": 0, "tn": 0, "fp": 0, "fn": 0}
    by_domain: dict[str, dict] = defaultdict(lambda: {"tp": 0, "tn": 0, "fp": 0, "fn": 0})
    scores_slop: list[float] = []
    scores_reviewed: list[float] = []
    errors = 0

    for i, s in enumerate(samples):
        if i % 200 == 0 and i > 0:
            print(f"  {i}/{len(samples)}...")
        try:
            r = score_text(s["text"], s.get("domain", "general"))
            predicted_slop = r.score < THRESHOLD
            actual_slop = s["label"] == "slop"

            if predicted_slop and actual_slop:
                matrix["tp"] += 1
            elif predicted_slop and not actual_slop:
                matrix["fp"] += 1
            elif not predicted_slop and actual_slop:
                matrix["fn"] += 1
            else:
                matrix["tn"] += 1

            d = s.get("domain", "general")
            if predicted_slop and actual_slop:
                by_domain[d]["tp"] += 1
            elif predicted_slop and not actual_slop:
                by_domain[d]["fp"] += 1
            elif not predicted_slop and actual_slop:
                by_domain[d]["fn"] += 1
            else:
                by_domain[d]["tn"] += 1

            if actual_slop:
                scores_slop.append(r.score)
            else:
                scores_reviewed.append(r.score)

        except Exception as e:
            errors += 1

    n = sum(matrix.values())
    precision = matrix["tp"] / max(matrix["tp"] + matrix["fp"], 1)
    recall = matrix["tp"] / max(matrix["tp"] + matrix["fn"], 1)
    f1 = 2 * precision * recall / max(precision + recall, 1e-9)
    accuracy = (matrix["tp"] + matrix["tn"]) / max(n, 1)

    avg_slop = sum(scores_slop) / max(len(scores_slop), 1)
    avg_reviewed = sum(scores_reviewed) / max(len(scores_reviewed), 1)

    # Per-domain
    domain_results = {}
    for domain, m in sorted(by_domain.items()):
        dn = sum(m.values())
        dp = m["tp"] / max(m["tp"] + m["fp"], 1)
        dr = m["tp"] / max(m["tp"] + m["fn"], 1)
        df1 = 2 * dp * dr / max(dp + dr, 1e-9)
        domain_results[domain] = {
            "f1": round(df1, 3),
            "precision": round(dp, 3),
            "recall": round(dr, 3),
            "n": dn,
        }

    result = {
        "dataset": str(path.name),
        "label": label,
        "total_samples": n,
        "errors": errors,
        "precision": round(precision, 4),
        "recall": round(recall, 4),
        "f1": round(f1, 4),
        "accuracy": round(accuracy, 4),
        "avg_score_slop": round(avg_slop, 2),
        "avg_score_reviewed": round(avg_reviewed, 2),
        "score_gap": round(avg_reviewed - avg_slop, 2),
        "confusion_matrix": matrix,
        "per_domain": domain_results,
    }

    # Print summary
    print(f"\n{'='*55}")
    print(f"RESULTS: {label or path.name}")
    print(f"{'='*55}")
    print(f"  Samples:   {n}  (errors: {errors})")
    print(f"  F1:        {result['f1']:.4f}")
    print(f"  Precision: {result['precision']:.4f}")
    print(f"  Recall:    {result['recall']:.4f}")
    print(f"  Accuracy:  {result['accuracy']:.4f}")
    print(f"  Avg slop score:     {result['avg_score_slop']:.1f}")
    print(f"  Avg reviewed score: {result['avg_score_reviewed']:.1f}")
    print(f"  Score gap:          {result['score_gap']:+.1f} pts")
    print(f"\n  Per-domain:")
    for domain, dm in domain_results.items():
        print(f"    {domain:<20} F1={dm['f1']:.3f}  n={dm['n']}")
    print(f"{'='*55}\n")

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Load external datasets for SlopGuard")
    parser.add_argument("--hc3", action="store_true", help="Load HC3 dataset")
    parser.add_argument("--raid", action="store_true", help="Load RAID benchmark")
    parser.add_argument("--hc3-subset", default="all", help="HC3 subset (all/reddit/wiki/medicine/finance)")
    parser.add_argument("--max", type=int, default=1000, help="Max samples per label per source")
    parser.add_argument("--evaluate", action="store_true", help="Run evaluation after loading")
    parser.add_argument("--eval-only", default="", help="Evaluate an existing dataset file")
    args = parser.parse_args()

    all_results = {}

    if args.eval_only:
        p = Path(args.eval_only)
        if not p.exists():
            p = SAMPLES_DIR / args.eval_only
        result = evaluate_dataset(p, label=p.stem)
        out = SAMPLES_DIR.parent / "hc3_results.json"
        out.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"Results saved → {out}")
        return

    if args.hc3:
        if args.hc3_subset == "all":
            hc3_samples = load_hc3_all_subsets(max_per_subset=args.max)
        else:
            hc3_samples = load_hc3(subset=args.hc3_subset, max_per_label=args.max)

        if hc3_samples:
            # Save standalone HC3 file
            hc3_path = SAMPLES_DIR / "hc3_slopguard.json"
            hc3_path.write_text(json.dumps(hc3_samples, indent=2), encoding="utf-8")
            print(f"Saved HC3 → {hc3_path} ({len(hc3_samples)} samples)")

            if args.evaluate:
                all_results["hc3"] = evaluate_dataset(hc3_path, label="HC3 Benchmark")

    if args.raid:
        raid_samples = load_raid(max_samples=args.max * 2)

        if raid_samples:
            raid_path = SAMPLES_DIR / "raid_slopguard.json"
            raid_path.write_text(json.dumps(raid_samples, indent=2), encoding="utf-8")
            print(f"Saved RAID → {raid_path} ({len(raid_samples)} samples)")

            if args.evaluate:
                all_results["raid"] = evaluate_dataset(raid_path, label="RAID Benchmark")

    # Merge everything into one big dataset
    if args.hc3 or args.raid:
        all_new: list[dict] = []
        for fname in ["hc3_slopguard.json", "raid_slopguard.json"]:
            p = SAMPLES_DIR / fname
            if p.exists():
                all_new.extend(json.loads(p.read_text(encoding="utf-8")))

        if all_new:
            merged_path = merge_and_save(all_new, "merged_dataset.json")
            if args.evaluate:
                all_results["merged"] = evaluate_dataset(merged_path, label="Full Merged Dataset")

    # Save all results
    if all_results:
        results_path = BASE / "datasets" / "hc3_results.json"
        results_path.write_text(json.dumps(all_results, indent=2), encoding="utf-8")
        print(f"\nAll results saved → {results_path}")

        # Print final summary table
        print("\n" + "=" * 55)
        print("FINAL SUMMARY")
        print("=" * 55)
        print(f"{'Dataset':<20} {'F1':>6} {'Prec':>6} {'Recall':>6} {'N':>6} {'Gap':>6}")
        print("-" * 55)
        for name, r in all_results.items():
            print(f"{name:<20} {r['f1']:>6.4f} {r['precision']:>6.4f} {r['recall']:>6.4f} {r['total_samples']:>6} {r['score_gap']:>+6.1f}")
        print("=" * 55)


if __name__ == "__main__":
    main()
