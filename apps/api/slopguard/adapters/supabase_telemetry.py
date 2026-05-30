"""Supabase client wrapper for opt-in telemetry and cross-device sync.

When supabase-py is installed and SUPABASE_URL + SUPABASE_KEY env vars are set,
this module provides persistent storage for score events, feedback, and user profiles.
Falls back to in-memory storage (the current behavior) when unavailable.
"""

from __future__ import annotations

import logging
import os
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

_client = None
_enabled = False


def _init_client() -> Any:
    """Lazy-initialize the Supabase client."""
    global _client, _enabled
    if _client is not None:
        return _client

    url = os.environ.get("SUPABASE_URL", "")
    key = os.environ.get("SUPABASE_KEY", "")

    if not url or not key:
        _enabled = False
        logger.debug("Supabase not configured (missing SUPABASE_URL or SUPABASE_KEY)")
        return None

    try:
        from supabase import create_client
        _client = create_client(url, key)
        _enabled = True
        logger.info("Supabase client initialized for %s", url)
        return _client
    except ImportError:
        _enabled = False
        logger.debug("supabase package not installed")
        return None
    except Exception as exc:
        _enabled = False
        logger.warning("Supabase initialization failed: %s", exc)
        return None


def is_enabled() -> bool:
    """Return True if Supabase is available and configured."""
    _init_client()
    return _enabled


def insert_score_event(
    user_id: str,
    url: str,
    title: str,
    domain: str,
    score: float,
    oversight: str,
    signals: list[dict] | None = None,
) -> dict:
    """Insert a score event into Supabase. Falls back to local dict if unavailable."""
    client = _init_client()
    event = {
        "user_id": user_id,
        "url": url,
        "title": title,
        "domain": domain,
        "score": score,
        "oversight": oversight,
        "signals": signals or [],
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    if client:
        try:
            result = client.table("score_events").insert(event).execute()
            return {"status": "persisted", "source": "supabase", "event": event}
        except Exception as exc:
            logger.warning("Supabase insert failed: %s", exc)

    return {"status": "persisted", "source": "local_fallback", "event": event}


def insert_feedback(
    user_id: str,
    event_id: str,
    user_label: str,
    notes: str = "",
) -> dict:
    """Insert user feedback into Supabase. Falls back to local dict."""
    client = _init_client()
    feedback = {
        "user_id": user_id,
        "event_id": event_id,
        "user_label": user_label,
        "notes": notes,
        "created_at": datetime.now(timezone.utc).isoformat(),
    }

    if client:
        try:
            result = client.table("feedback_events").insert(feedback).execute()
            return {"status": "recorded", "source": "supabase", "feedback": feedback}
        except Exception as exc:
            logger.warning("Supabase feedback insert failed: %s", exc)

    return {"status": "recorded", "source": "local_fallback", "feedback": feedback}


def get_user_summary(user_id: str, limit: int = 50) -> dict:
    """Get a user's score summary from Supabase. Falls back to empty."""
    client = _init_client()
    if not client:
        return {"total_scored": 0, "source": "local_fallback"}

    try:
        events = (
            client.table("score_events")
            .select("*")
            .eq("user_id", user_id)
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        data = events.data if hasattr(events, "data") else []

        total = len(data)
        if total == 0:
            return {"total_scored": 0, "source": "supabase"}

        scores = [e.get("score", 0) for e in data]
        low_count = sum(1 for e in data if e.get("oversight") == "low")

        # Group by domain
        by_domain: dict[str, list[float]] = {}
        for e in data:
            d = e.get("domain", "general")
            by_domain.setdefault(d, []).append(e.get("score", 0))

        domain_avgs = {
            d: round(sum(s) / len(s), 1) for d, s in by_domain.items()
        }

        return {
            "total_scored": total,
            "average_score": round(sum(scores) / total, 1),
            "low_oversight_percent": round((low_count / total) * 100, 1),
            "by_domain": domain_avgs,
            "recent": data[:10],
            "source": "supabase",
        }
    except Exception as exc:
        logger.warning("Supabase query failed: %s", exc)
        return {"total_scored": 0, "source": "supabase_error", "error": str(exc)}


def upsert_user_profile(user_id: str, profile: dict) -> dict:
    """Upsert a user profile in Supabase."""
    client = _init_client()
    if not client:
        return {"status": "skipped", "source": "local_fallback"}

    data = {"user_id": user_id, **profile, "updated_at": datetime.now(timezone.utc).isoformat()}
    try:
        result = client.table("user_profiles").upsert(data).execute()
        return {"status": "updated", "source": "supabase"}
    except Exception as exc:
        return {"status": "failed", "source": "supabase", "error": str(exc)}


def get_site_leaderboard(category: str = "", limit: int = 50) -> dict:
    """Get site trust leaderboard from Supabase telemetry.

    Aggregates score_events by URL domain, computing average trust score.
    Falls back to empty dict if Supabase is not configured.
    """
    client = _init_client()
    if not client:
        return {"items": [], "source": "local_fallback", "note": "Configure SUPABASE_URL and SUPABASE_KEY for live leaderboards"}

    try:
        events = (
            client.table("score_events")
            .select("url, score, domain, created_at")
            .order("created_at", desc=True)
            .limit(5000)
            .execute()
        )
        data = events.data if hasattr(events, "data") else []

        if not data:
            return {"items": [], "source": "supabase", "total_events": 0}

        # Aggregate by domain
        from urllib.parse import urlparse
        domain_scores: dict[str, list[float]] = {}
        for e in data:
            url = e.get("url", "")
            if not url:
                continue
            try:
                parsed = urlparse(url)
                domain = parsed.hostname or url.split("/")[0]
            except Exception:
                domain = url.split("/")[0]

            if category and category.lower() not in domain.lower():
                continue

            domain_scores.setdefault(domain, []).append(e.get("score", 0))

        # Compute averages and trends
        items = []
        for domain, scores in domain_scores.items():
            avg_score = sum(scores) / len(scores)
            # Simple trend: compare last 25% vs first 75%
            midpoint = len(scores) // 4
            if midpoint > 0:
                recent_avg = sum(scores[:midpoint]) / midpoint
                older_avg = sum(scores[midpoint:]) / (len(scores) - midpoint)
                trend = recent_avg - older_avg
            else:
                trend = 0.0

            items.append({
                "domain": domain,
                "score": round(avg_score, 1),
                "trend": f"+{trend:.1f}" if trend >= 0 else f"{trend:.1f}",
                "sample_count": len(scores),
            })

        items.sort(key=lambda x: x["score"], reverse=True)
        return {"items": items[:limit], "source": "supabase", "total_events": len(data)}

    except Exception as exc:
        logger.warning("Supabase leaderboard query failed: %s", exc)
        return {"items": [], "source": "supabase_error", "error": str(exc)}


def get_repo_leaderboard(org: str = "", limit: int = 50) -> dict:
    """Get repo oversight leaderboard from Supabase telemetry.

    Aggregates score_events by repository, computing average oversight score
    and reviewer impact proxy.
    Falls back to empty dict if Supabase is not configured.
    """
    client = _init_client()
    if not client:
        return {"items": [], "source": "local_fallback", "note": "Configure SUPABASE_URL and SUPABASE_KEY for live leaderboards"}

    try:
        events = (
            client.table("score_events")
            .select("url, title, score, signals, domain, created_at")
            .eq("domain", "code_review")
            .order("created_at", desc=True)
            .limit(5000)
            .execute()
        )
        data = events.data if hasattr(events, "data") else []

        if not data:
            return {"items": [], "source": "supabase", "total_events": 0}

        # Aggregate by repo (extract from URL)
        import re
        repo_scores: dict[str, list[dict]] = {}
        for e in data:
            url = e.get("url", "")
            # Extract owner/repo from GitHub URLs
            match = re.search(r"github\.com/([^/]+/[^/]+)", url)
            if not match:
                continue
            repo = match.group(1)

            if org and not repo.startswith(org + "/"):
                continue

            # Extract reviewer impact from signals
            reviewer_impact = 0.5
            signals = e.get("signals", [])
            if isinstance(signals, list):
                for s in signals:
                    if s.get("name") == "reviewer_impact_proxy":
                        reviewer_impact = s.get("score", 0.5)
                        break

            repo_scores.setdefault(repo, []).append({
                "score": e.get("score", 0),
                "reviewer_impact": reviewer_impact,
            })

        items = []
        for repo, entries in repo_scores.items():
            avg_score = sum(e["score"] for e in entries) / len(entries)
            avg_impact = sum(e["reviewer_impact"] for e in entries) / len(entries)
            items.append({
                "repo": repo,
                "score": round(avg_score, 1),
                "reviewer_impact": round(avg_impact, 2),
                "pr_count": len(entries),
            })

        items.sort(key=lambda x: x["score"], reverse=True)
        return {"items": items[:limit], "source": "supabase", "total_events": len(data)}

    except Exception as exc:
        logger.warning("Supabase repo leaderboard query failed: %s", exc)
        return {"items": [], "source": "supabase_error", "error": str(exc)}
