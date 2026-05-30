"""Live Slop Ticker — aggregates scoring events into real-time snapshots.

Queries the in-memory score log (or Supabase when configured) to produce
60-second-window summaries showing domain averages, top signals, and trends.
"""

from __future__ import annotations

import time
from collections import defaultdict
from typing import Any

from slopguard.adapters.baselines import get_raw_stores


def get_ticker_snapshot() -> dict:
    """Aggregate the last 60 seconds of scoring activity."""
    _, _, global_baselines, score_log = get_raw_stores()
    now = time.time()
    cutoff = now - 60

    recent = [e for e in score_log if e["timestamp"] >= cutoff]
    previous = [e for e in score_log if cutoff - 60 <= e["timestamp"] < cutoff]

    total_scored = len(recent)
    if total_scored == 0:
        # Check if there's any history at all (not just the last 60s)
        if not score_log:
            return {
                "state": "warming_up",
                "message": "Score some content to see live stats",
                "total_scored": 0,
            }
        return _empty_snapshot(global_baselines)

    # Domain averages
    domain_data: dict[str, list[float]] = defaultdict(list)
    domain_prev: dict[str, list[float]] = defaultdict(list)
    for e in recent:
        domain_data[e["domain"]].append(e["score"])
    for e in previous:
        domain_prev[e["domain"]].append(e["score"])

    domain_averages = {}
    for domain, scores in domain_data.items():
        avg = sum(scores) / len(scores)
        prev_scores = domain_prev.get(domain, [])
        delta = (sum(prev_scores) / len(prev_scores) - avg) if prev_scores else 0.0
        domain_averages[domain] = {
            "avg": round(avg, 1),
            "delta": round(delta, 1),
            "count": len(scores),
        }

    # Top signal
    signal_counts: dict[str, int] = defaultdict(int)
    for e in recent:
        signal_counts[e["top_signal"]] += 1
    top_signal = max(signal_counts, key=signal_counts.get) if signal_counts else "unknown"
    top_signal_rate = round(signal_counts[top_signal] / total_scored, 2) if total_scored > 0 else 0.0

    # Hottest repo
    repo_data: dict[str, list[float]] = defaultdict(list)
    for e in recent:
        if e.get("repo_id"):
            repo_data[e["repo_id"]].append(e["score"])
    hottest_repo = None
    if repo_data:
        by_count = sorted(repo_data.items(), key=lambda kv: len(kv[1]), reverse=True)
        top_repo, top_scores = by_count[0]
        hottest_repo = {
            "name": top_repo,
            "count": len(top_scores),
            "avg": round(sum(top_scores) / len(top_scores), 1),
        }

    # Global avg
    global_avg = 50.0
    global_delta = 0.0
    for domain, gb in global_baselines.items():
        if gb.sample_count > 0:
            global_avg = gb.mean_score
            break

    prev_global = [e["score"] for e in previous]
    if prev_global:
        prev_avg = sum(prev_global) / len(prev_global)
        global_delta = round(global_avg - prev_avg, 1)
    else:
        global_delta = 0.0

    slop_count = sum(1 for e in recent if e.get("is_slop", False))
    slop_rate = round(slop_count / total_scored, 2) if total_scored > 0 else 0.0

    return {
        "window_seconds": 60,
        "total_scored": total_scored,
        "domain_averages": domain_averages,
        "top_signal": top_signal,
        "top_signal_rate": top_signal_rate,
        "hottest_repo": hottest_repo,
        "global_avg": round(global_avg, 1),
        "global_delta": global_delta,
        "slop_rate": slop_rate,
        "timestamp": now,
    }


def _empty_snapshot(global_baselines: dict) -> dict:
    domain_averages = {}
    for domain, gb in global_baselines.items():
        if gb.sample_count > 0:
            domain_averages[domain] = {
                "avg": round(gb.mean_score, 1),
                "delta": 0.0,
                "count": gb.sample_count,
            }

    return {
        "window_seconds": 60,
        "total_scored": 0,
        "domain_averages": domain_averages,
        "top_signal": "unknown",
        "top_signal_rate": 0.0,
        "hottest_repo": None,
        "global_avg": 50.0,
        "global_delta": 0.0,
        "slop_rate": 0.0,
        "timestamp": time.time(),
    }


class TickerEventStream:
    """Simple in-memory event source for SSE ticker updates."""

    def __init__(self) -> None:
        self._listeners: list[__import__("asyncio").Queue] = []
        self._last_snapshot: dict | None = None

    def get_last_snapshot(self) -> dict | None:
        return self._last_snapshot

    def publish(self, snapshot: dict) -> None:
        self._last_snapshot = snapshot
        import asyncio
        dead: list[__import__("asyncio").Queue] = []
        for q in self._listeners:
            try:
                q.put_nowait(snapshot)
            except asyncio.QueueFull:
                dead.append(q)
        for q in dead:
            self._listeners.remove(q)

    def subscribe(self) -> __import__("asyncio").Queue:
        import asyncio
        q: asyncio.Queue = asyncio.Queue(maxsize=32)
        self._listeners.append(q)
        return q

    def unsubscribe(self, q: __import__("asyncio").Queue) -> None:
        if q in self._listeners:
            self._listeners.remove(q)


_ticker_stream = TickerEventStream()


def get_ticker_stream_instance() -> TickerEventStream:
    return _ticker_stream


def refresh_and_publish() -> dict:
    snapshot = get_ticker_snapshot()
    _ticker_stream.publish(snapshot)
    return snapshot
