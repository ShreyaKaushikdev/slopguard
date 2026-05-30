"""Adaptive Domain Baselines — per-repo, per-author, and global baseline tracking.

Stores incremental mean/stddev statistics so we never need to retain
all historical scores. Called after every scoring event to update baselines,
and queried to produce relative scores with context-aware verdicts.
"""

from __future__ import annotations

import math
import time
from dataclasses import dataclass, field
from typing import Literal


# ---------------------------------------------------------------------------
# In-memory stores (drop-in replace with Supabase when configured)
# ---------------------------------------------------------------------------

_repo_baselines: dict[str, "RepoBaseline"] = {}
_author_baselines: dict[str, "AuthorBaseline"] = {}
_global_baselines: dict[str, "GlobalBaseline"] = {}
_score_log: list[dict] = []


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class RepoBaseline:
    repo_id: str
    domain: str
    sample_count: int = 0
    mean_score: float = 0.0
    m2: float = 0.0  # sum of squared differences from current mean (for stddev)
    min_score: float = 100.0
    max_score: float = 0.0
    last_updated: float = 0.0

    @property
    def std_dev(self) -> float:
        if self.sample_count < 2:
            return 0.0
        return math.sqrt(self.m2 / (self.sample_count - 1))

    @property
    def variance(self) -> float:
        return self.std_dev ** 2

    def percentiles(self) -> dict[str, float]:
        return {"p25": 0.0, "p50": 0.0, "p75": 0.0, "p90": 0.0}


@dataclass
class AuthorBaseline:
    author_id: str
    repo_id: str
    domain: str
    sample_count: int = 0
    mean_score: float = 0.0
    m2: float = 0.0
    min_score: float = 100.0
    max_score: float = 0.0
    why_ratio_sum: float = 0.0
    specificity_sum: float = 0.0
    last_updated: float = 0.0

    @property
    def std_dev(self) -> float:
        if self.sample_count < 2:
            return 0.0
        return math.sqrt(self.m2 / (self.sample_count - 1))

    @property
    def why_ratio(self) -> float:
        if self.sample_count == 0:
            return 0.0
        return self.why_ratio_sum / self.sample_count

    @property
    def specificity_mean(self) -> float:
        if self.sample_count == 0:
            return 0.0
        return self.specificity_sum / self.sample_count


@dataclass
class GlobalBaseline:
    domain: str
    sample_count: int = 0
    mean_score: float = 0.0
    m2: float = 0.0
    min_score: float = 100.0
    max_score: float = 0.0
    last_updated: float = 0.0

    @property
    def std_dev(self) -> float:
        if self.sample_count < 2:
            return 0.0
        return math.sqrt(self.m2 / (self.sample_count - 1))


# ---------------------------------------------------------------------------
# Incremental statistics (Welford's online algorithm)
# ---------------------------------------------------------------------------

def update_incremental_mean(old_mean: float, m2: float, old_count: int, new_value: float) -> tuple[float, float, int]:
    new_count = old_count + 1
    delta = new_value - old_mean
    new_mean = old_mean + delta / new_count
    delta2 = new_value - new_mean
    new_m2 = m2 + delta * delta2
    return new_mean, new_m2, new_count


def _find_author_baseline_key(author_id: str, repo_id: str, domain: str) -> str:
    return f"{author_id}|{repo_id}|{domain}"


# ---------------------------------------------------------------------------
# Core update function — called after every scoring event
# ---------------------------------------------------------------------------

def update_baseline(
    repo_id: str | None = None,
    author_id: str | None = None,
    domain: str = "general",
    score: float = 50.0,
    signals: list | None = None,
) -> None:
    now = time.time()

    # --- Global baseline ---
    if domain not in _global_baselines:
        _global_baselines[domain] = GlobalBaseline(domain=domain, last_updated=now)
    gb = _global_baselines[domain]
    gb.mean_score, gb.m2, gb.sample_count = update_incremental_mean(
        gb.mean_score, gb.m2, gb.sample_count, score
    )
    gb.min_score = min(gb.min_score, score)
    gb.max_score = max(gb.max_score, score)
    gb.last_updated = now

    # --- Repo baseline ---
    if repo_id:
        key = f"{repo_id}|{domain}"
        if key not in _repo_baselines:
            _repo_baselines[key] = RepoBaseline(
                repo_id=repo_id, domain=domain, last_updated=now
            )
        rb = _repo_baselines[key]
        rb.mean_score, rb.m2, rb.sample_count = update_incremental_mean(
            rb.mean_score, rb.m2, rb.sample_count, score
        )
        rb.min_score = min(rb.min_score, score)
        rb.max_score = max(rb.max_score, score)
        rb.last_updated = now

    # --- Author baseline ---
    if author_id and repo_id:
        ak = _find_author_baseline_key(author_id, repo_id, domain)
        if ak not in _author_baselines:
            _author_baselines[ak] = AuthorBaseline(
                author_id=author_id, repo_id=repo_id, domain=domain, last_updated=now
            )
        ab = _author_baselines[ak]
        ab.mean_score, ab.m2, ab.sample_count = update_incremental_mean(
            ab.mean_score, ab.m2, ab.sample_count, score
        )
        ab.min_score = min(ab.min_score, score)
        ab.max_score = max(ab.max_score, score)
        if signals:
            for s in (signals or []):
                if isinstance(s, dict):
                    if s.get("name") == "why_vs_what":
                        ab.why_ratio_sum += s.get("score", 0.0)
                    elif s.get("name") == "specificity":
                        ab.specificity_sum += s.get("score", 0.0)
        ab.last_updated = now

    # --- Log for ticker ---
    _score_log.append({
        "timestamp": now,
        "domain": domain,
        "repo_id": repo_id or "",
        "score": score,
        "top_signal": _find_top_signal(signals),
        "is_slop": score < (gb.mean_score if gb.sample_count > 0 else 50.0),
    })
    if len(_score_log) > 10000:
        _score_log[:5000] = []


def _find_top_signal(signals: list | None) -> str:
    if not signals:
        return "unknown"
    best = None
    best_score = float("inf")
    for s in signals:
        if isinstance(s, dict):
            sc = s.get("score", 0.5)
            if sc < best_score:
                best_score = sc
                best = s.get("name", "unknown")
    return best or "unknown"


# ---------------------------------------------------------------------------
# Relative score computation
# ---------------------------------------------------------------------------

ConfidenceLevel = Literal["high", "medium", "low", "none"]


def get_relative_score(
    raw_score: float,
    repo_id: str | None = None,
    author_id: str | None = None,
    domain: str = "general",
) -> dict:
    repo_mean: float | None = None
    repo_std: float | None = None
    repo_count: int = 0
    author_mean: float | None = None
    author_count: int = 0
    global_mean_val: float | None = None
    global_std_val: float | None = None

    # Global
    if domain in _global_baselines:
        gb = _global_baselines[domain]
        global_mean_val = gb.mean_score
        global_std_val = gb.std_dev

    # Repo
    if repo_id:
        rk = f"{repo_id}|{domain}"
        if rk in _repo_baselines:
            rb = _repo_baselines[rk]
            repo_mean = rb.mean_score
            repo_std = rb.std_dev
            repo_count = rb.sample_count

    # Author
    if author_id and repo_id:
        ak = _find_author_baseline_key(author_id, repo_id, domain)
        if ak in _author_baselines:
            ab = _author_baselines[ak]
            author_mean = ab.mean_score
            author_count = ab.sample_count

    # --- Baseline confidence ---
    sample_count = max(repo_count, author_count, (global_baseline_count(domain)))
    if sample_count >= 20:
        confidence: ConfidenceLevel = "high"
    elif sample_count >= 5:
        confidence = "medium"
    elif sample_count >= 2:
        confidence = "low"
    else:
        confidence = "none"

    # --- Percentiles (approximate from z-score) ---
    def approximate_percentile(value: float, mean: float | None, std: float | None) -> float | None:
        if mean is None or std is None or std == 0:
            return None
        z = (value - mean) / std
        return round(_normal_cdf(z) * 100)

    repo_percentile = approximate_percentile(raw_score, repo_mean, repo_std)
    global_percentile = approximate_percentile(raw_score, global_mean_val, global_std_val)

    # --- Verdict ---
    verdict = "insufficient_data"
    context = ""
    if repo_mean is not None and repo_std is not None and repo_std > 0:
        if raw_score > repo_mean + repo_std:
            verdict = "above_repo_standard"
            context = f"This scores higher than typical PRs in this repo."
        elif raw_score < repo_mean - repo_std:
            verdict = "below_repo_standard"
            below_pct = approximate_percentile(repo_mean - repo_std, repo_mean, repo_std)
            context = f"This scores lower than most PRs in this repo."
        else:
            verdict = "within_repo_norms"
            context = f"This is within the normal range for this repo."
    elif global_mean_val is not None and global_std_val is not None and global_std_val > 0:
        if raw_score > global_mean_val + global_std_val:
            verdict = "above_global_average"
            context = f"This scores higher than the global average for {domain}."
        elif raw_score < global_mean_val - global_std_val:
            verdict = "below_global_average"
            context = f"This scores lower than the global average for {domain}."
        else:
            verdict = "near_global_average"
            context = f"This is near the global average for {domain}."
    elif global_mean_val is not None:
        context = f"Building baseline — score 5+ items for contextual scoring."
    else:
        context = "No baseline data yet — scores will become more contextual over time."

    return {
        "raw": raw_score,
        "repo_mean": round(repo_mean, 1) if repo_mean is not None else None,
        "repo_percentile": repo_percentile,
        "author_mean": round(author_mean, 1) if author_mean is not None else None,
        "global_mean": round(global_mean_val, 1) if global_mean_val is not None else None,
        "global_percentile": global_percentile,
        "verdict": verdict,
        "context": context,
        "baseline_confidence": confidence,
    }


def global_baseline_count(domain: str) -> int:
    if domain in _global_baselines:
        return _global_baselines[domain].sample_count
    return 0


# ---------------------------------------------------------------------------
# Repo profile (for org dashboard)
# ---------------------------------------------------------------------------

def get_repo_profile(repo_id: str, domain: str = "code_review") -> dict:
    rk = f"{repo_id}|{domain}"
    rb = _repo_baselines.get(rk)

    if not rb:
        return {
            "repo_id": repo_id,
            "domain": domain,
            "status": "no_data",
            "sample_count": 0,
            "mean_score": None,
        }

    # Find authors for this repo
    authors = []
    for ak, ab in _author_baselines.items():
        if ab.repo_id == repo_id and ab.domain == domain:
            authors.append({
                "author_id": ab.author_id,
                "sample_count": ab.sample_count,
                "mean_score": round(ab.mean_score, 1),
                "why_ratio": round(ab.why_ratio, 3),
                "specificity_mean": round(ab.specificity_mean, 3),
            })

    return {
        "repo_id": repo_id,
        "domain": domain,
        "status": "active",
        "sample_count": rb.sample_count,
        "mean_score": round(rb.mean_score, 1),
        "std_dev": round(rb.std_dev, 2),
        "min_score": round(rb.min_score, 1),
        "max_score": round(rb.max_score, 1),
        "authors": sorted(authors, key=lambda a: a["sample_count"], reverse=True),
        "last_updated": rb.last_updated,
    }


# ---------------------------------------------------------------------------
# Z-score -> percentile helper
# ---------------------------------------------------------------------------

def _normal_cdf(x: float) -> float:
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


# ---------------------------------------------------------------------------
# Exposed for testing / seeding
# ---------------------------------------------------------------------------

def get_raw_stores() -> tuple:
    return _repo_baselines, _author_baselines, _global_baselines, _score_log


def clear_all() -> None:
    _repo_baselines.clear()
    _author_baselines.clear()
    _global_baselines.clear()
    _score_log.clear()
