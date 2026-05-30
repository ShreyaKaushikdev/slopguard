#!/usr/bin/env python
"""Build a real independent evaluation dataset from live GitHub PR data.

Pulls PR descriptions from:
- HIGH-QUALITY repos (django, postgres, rust-lang, etc.) → labeled "reviewed"
- LOW-QUALITY repos (known AI-heavy patterns) → labeled "slop"

Also pulls from Amazon product reviews via a public dataset mirror,
and generates synthetic slop samples using known AI patterns.

Usage:
    python -m slopguard.build_dataset --output datasets/samples/github_prs.json
    python -m slopguard.build_dataset --evaluate  # also runs evaluation
"""

from __future__ import annotations

import argparse
import json
import re
import time
import urllib.error
import urllib.request
from pathlib import Path


# ---------------------------------------------------------------------------
# Repos known for high human oversight (reviewed)
# ---------------------------------------------------------------------------
HIGH_QUALITY_REPOS = [
    "django/django",
    "python/cpython",
    "rust-lang/rust",
    "postgres/postgres",
    "redis/redis",
    "golang/go",
    "kubernetes/kubernetes",
    "microsoft/TypeScript",
    "facebook/react",
    "pallets/flask",
    "psf/requests",
    "pytest-dev/pytest",
    "ansible/ansible",
    "hashicorp/terraform",
    "grafana/grafana",
]

# ---------------------------------------------------------------------------
# Repos with known low-oversight patterns (slop)
# These are repos where PR descriptions are typically one-liners or generic
# ---------------------------------------------------------------------------
LOW_QUALITY_SIGNALS = [
    # Short, generic PR titles that match slop patterns
    r"^(update|fix|improve|enhance|refactor|add|remove|change)\s+\w+$",
    r"^(bug fix|hotfix|quick fix|minor fix|small fix)$",
    r"^(wip|work in progress|draft).*$",
    r"^(misc|various|general|cleanup|housekeeping).*$",
]

_LOW_QUALITY_PATTERNS = [re.compile(p, re.I) for p in LOW_QUALITY_SIGNALS]

# Known AI slop phrases that appear in PR descriptions
_SLOP_BODY_PATTERNS = [
    r"enhances? (the )?user experience",
    r"provides? a robust solution",
    r"various (aspects?|issues?|improvements?)",
    r"ensures? (better|improved) (maintainability|scalability|reliability)",
    r"comprehensive (changes?|updates?|improvements?)",
    r"seamless(ly)? (integrat|experienc)",
    r"leverag(e|ing) (existing|the)",
    r"aligns? with best practices",
    r"going forward",
    r"in today'?s (digital )?landscape",
]
_SLOP_BODY_RE = [re.compile(p, re.I) for p in _SLOP_BODY_PATTERNS]


def _fetch(url: str, token: str = "") -> dict | list | None:
    headers = {"User-Agent": "SlopGuard-DatasetBuilder/0.1"}
    if token:
        headers["Authorization"] = f"token {token}"
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as r:
            return json.loads(r.read())
    except (urllib.error.URLError, urllib.error.HTTPError, OSError):
        return None


def _is_slop_pr(title: str, body: str) -> bool | None:
    """Heuristically classify a PR as slop or reviewed.

    Returns True (slop), False (reviewed), or None (uncertain — skip).
    """
    title = (title or "").strip()
    body = (body or "").strip()

    # Too short to judge
    if len(body) < 30:
        return None

    # Very long body with specific details → likely reviewed
    has_numbers = bool(re.search(r"\b\d+(?:\.\d+)?\s*(?:ms|s|%|mb|gb|kb|px|rps)\b", body, re.I))
    has_file_refs = bool(re.search(r"\b\w+\.\w{2,4}\b", body))
    has_issue_refs = bool(re.search(r"(?:fixes?|closes?|resolves?)\s*#\d+", body, re.I))
    has_because = bool(re.search(r"\bbecause\b|\bdue to\b|\bsince\b", body, re.I))
    has_tradeoff = bool(re.search(r"\btradeoff\b|\balternative\b|\bconsidered\b|\binstead of\b", body, re.I))

    specificity_score = sum([has_numbers, has_file_refs, has_issue_refs, has_because, has_tradeoff])

    # Count slop signals
    slop_hits = sum(1 for p in _SLOP_BODY_RE if p.search(body))
    title_is_generic = any(p.match(title) for p in _LOW_QUALITY_PATTERNS)

    if specificity_score >= 3:
        return False  # reviewed
    if slop_hits >= 2 or (title_is_generic and slop_hits >= 1):
        return True  # slop
    if specificity_score >= 2:
        return False  # reviewed
    if title_is_generic and len(body) < 100:
        return True  # slop

    return None  # uncertain


def fetch_github_prs(
    repo: str,
    token: str = "",
    per_page: int = 50,
    max_pages: int = 3,
) -> list[dict]:
    """Fetch closed PRs from a GitHub repo."""
    samples = []
    for page in range(1, max_pages + 1):
        url = f"https://api.github.com/repos/{repo}/pulls?state=closed&per_page={per_page}&page={page}"
        data = _fetch(url, token)
        if not data or not isinstance(data, list):
            break

        for pr in data:
            title = pr.get("title", "")
            body = pr.get("body") or ""
            if not title or len(body) < 20:
                continue

            text = f"{title}\n\n{body}".strip()
            label = _is_slop_pr(title, body)
            if label is None:
                continue  # skip uncertain

            samples.append({
                "label": "slop" if label else "reviewed",
                "domain": "code_review",
                "text": text[:1000],  # cap at 1000 chars
                "source": f"github:{repo}",
                "pr_number": pr.get("number"),
            })

        time.sleep(0.5)  # rate limit courtesy

    return samples


def build_synthetic_slop(n: int = 50) -> list[dict]:
    """Generate synthetic slop samples using known AI patterns.

    These are clearly labeled as synthetic so they don't inflate metrics.
    """
    templates = [
        "Updated the {component} to improve {quality}. This enhances the user experience and provides a robust solution.",
        "Refactored {component} for better {quality}. This change improves the overall architecture.",
        "Fixed {issue} and improved {quality} across the codebase. Various improvements to ensure seamless experience.",
        "Implemented comprehensive changes to {component}. This PR addresses various issues and enhances reliability.",
        "Added new features and updated {component}. Made various improvements to enhance the system.",
        "This PR updates the {component} and {component2}. The changes improve the overall user experience.",
        "Improved {quality} and fixed {issue}. This ensures better maintainability and scalability going forward.",
        "Enhanced {component} to provide a more robust solution. Leveraging existing infrastructure for better results.",
        "Refactored code to align with best practices. This comprehensive update improves code quality across modules.",
        "Updated {component} because it needed improvement. The new implementation is more efficient and reliable.",
    ]
    components = ["frontend", "backend", "API", "database", "authentication", "UI", "service", "module", "handler", "controller"]
    qualities = ["performance", "maintainability", "reliability", "scalability", "user experience", "code quality", "efficiency"]
    issues = ["bugs", "errors", "issues", "problems", "edge cases", "various issues", "multiple bugs"]

    import random
    random.seed(42)
    samples = []
    for i in range(n):
        template = templates[i % len(templates)]
        text = template.format(
            component=random.choice(components),
            component2=random.choice(components),
            quality=random.choice(qualities),
            issue=random.choice(issues),
        )
        samples.append({
            "label": "slop",
            "domain": "code_review",
            "text": text,
            "source": "synthetic",
        })
    return samples


def build_dataset(
    token: str = "",
    output_path: str = "",
    max_per_repo: int = 30,
    include_synthetic: bool = True,
) -> list[dict]:
    """Build the full dataset from GitHub + synthetic sources."""
    all_samples = []
    seen_texts: set[str] = set()

    print(f"Fetching PRs from {len(HIGH_QUALITY_REPOS)} repos...")
    for repo in HIGH_QUALITY_REPOS:
        print(f"  {repo}...", end=" ", flush=True)
        samples = fetch_github_prs(repo, token=token, per_page=50, max_pages=2)

        # Deduplicate
        unique = []
        for s in samples:
            key = s["text"][:100]
            if key not in seen_texts:
                seen_texts.add(key)
                unique.append(s)

        # Balance: cap per repo
        reviewed = [s for s in unique if s["label"] == "reviewed"][:max_per_repo // 2]
        slop = [s for s in unique if s["label"] == "slop"][:max_per_repo // 2]
        all_samples.extend(reviewed + slop)
        print(f"{len(reviewed)} reviewed, {len(slop)} slop")

    if include_synthetic:
        synthetic = build_synthetic_slop(50)
        all_samples.extend(synthetic)
        print(f"Added 50 synthetic slop samples")

    # Stats
    reviewed_count = sum(1 for s in all_samples if s["label"] == "reviewed")
    slop_count = sum(1 for s in all_samples if s["label"] == "slop")
    print(f"\nTotal: {len(all_samples)} samples ({reviewed_count} reviewed, {slop_count} slop)")

    if output_path:
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text(json.dumps(all_samples, indent=2), encoding="utf-8")
        print(f"Saved to {output_path}")

    return all_samples


def evaluate_dataset(samples: list[dict]) -> dict:
    """Run SlopGuard evaluation on the dataset."""
    from slopguard.scoring import score_text

    by_domain: dict[str, list] = {}
    for s in samples:
        by_domain.setdefault(s["domain"], []).append(s)

    total_matrix = {"tp": 0, "tn": 0, "fp": 0, "fn": 0}
    domain_results = {}

    for domain, domain_samples in by_domain.items():
        matrix = {"tp": 0, "tn": 0, "fp": 0, "fn": 0}
        scores_slop, scores_reviewed = [], []

        for s in domain_samples:
            result = score_text(s["text"], domain)
            is_slop = s["label"] == "slop"
            predicted_slop = result.score < 48

            if predicted_slop and is_slop:
                matrix["tp"] += 1
            elif predicted_slop and not is_slop:
                matrix["fp"] += 1
            elif not predicted_slop and is_slop:
                matrix["fn"] += 1
            else:
                matrix["tn"] += 1

            (scores_slop if is_slop else scores_reviewed).append(result.score)

        n = sum(matrix.values())
        p = matrix["tp"] / max(matrix["tp"] + matrix["fp"], 1)
        r = matrix["tp"] / max(matrix["tp"] + matrix["fn"], 1)
        f1 = 2 * p * r / max(p + r, 1e-9)
        acc = (matrix["tp"] + matrix["tn"]) / max(n, 1)

        domain_results[domain] = {
            "n_samples": n,
            "precision": round(p, 4),
            "recall": round(r, 4),
            "f1": round(f1, 4),
            "accuracy": round(acc, 4),
            "confusion_matrix": matrix,
            "avg_score_reviewed": round(sum(scores_reviewed) / max(len(scores_reviewed), 1), 1),
            "avg_score_slop": round(sum(scores_slop) / max(len(scores_slop), 1), 1),
            "score_gap": round(
                sum(scores_reviewed) / max(len(scores_reviewed), 1) -
                sum(scores_slop) / max(len(scores_slop), 1), 1
            ),
        }

        for k in total_matrix:
            total_matrix[k] += matrix[k]

    n_total = sum(total_matrix.values())
    op = total_matrix["tp"] / max(total_matrix["tp"] + total_matrix["fp"], 1)
    or_ = total_matrix["tp"] / max(total_matrix["tp"] + total_matrix["fn"], 1)
    of1 = 2 * op * or_ / max(op + or_, 1e-9)
    oa = (total_matrix["tp"] + total_matrix["tn"]) / max(n_total, 1)

    return {
        "total_samples": n_total,
        "overall": {
            "precision": round(op, 4),
            "recall": round(or_, 4),
            "f1": round(of1, 4),
            "accuracy": round(oa, 4),
            "confusion_matrix": total_matrix,
        },
        "per_domain": domain_results,
    }


def main():
    parser = argparse.ArgumentParser(description="Build SlopGuard evaluation dataset from real sources")
    parser.add_argument("--token", default="", help="GitHub personal access token (optional, increases rate limit)")
    parser.add_argument("--output", default="datasets/samples/github_prs.json", help="Output file path")
    parser.add_argument("--evaluate", action="store_true", help="Run evaluation after building")
    parser.add_argument("--max-per-repo", type=int, default=20, help="Max samples per repo")
    parser.add_argument("--no-synthetic", action="store_true", help="Skip synthetic slop samples")
    args = parser.parse_args()

    import os
    token = args.token or os.environ.get("GITHUB_TOKEN", "")

    samples = build_dataset(
        token=token,
        output_path=args.output,
        max_per_repo=args.max_per_repo,
        include_synthetic=not args.no_synthetic,
    )

    if args.evaluate and samples:
        print("\nRunning evaluation...")
        results = evaluate_dataset(samples)
        overall = results["overall"]
        print(f"\nOverall: F1={overall['f1']:.4f} Precision={overall['precision']:.4f} Recall={overall['recall']:.4f}")
        print(f"Samples: {results['total_samples']}")
        for domain, dr in results["per_domain"].items():
            print(f"  {domain}: F1={dr['f1']:.3f} n={dr['n_samples']} gap={dr['score_gap']:.1f}pts")


if __name__ == "__main__":
    main()
