"""GitHub OAuth adapter for timeline ingestion and real Slop Velocity.

Provides OAuth flow endpoints and PR timeline fetching for real developer activity data.
Requires GITHUB_CLIENT_ID and GITHUB_CLIENT_SECRET env vars.
"""

from __future__ import annotations

import json
import logging
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

_CLIENT_ID = os.environ.get("GITHUB_CLIENT_ID", "")
_CLIENT_SECRET = os.environ.get("GITHUB_CLIENT_SECRET", "")
_REDIRECT_URI = os.environ.get("GITHUB_REDIRECT_URI", "http://localhost:8000/auth/github/callback")

_tokens: dict[str, dict] = {}  # Simple in-memory token store


def _fetch_github(url: str, token: str) -> Any:
    """Fetch from GitHub API with authentication."""
    try:
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/vnd.github+json",
                "User-Agent": "SlopGuard/0.1",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        logger.warning("GitHub API fetch failed for %s: %s", url, exc)
        return None


def get_auth_url(state: str = "") -> str:
    """Generate GitHub OAuth authorization URL."""
    if not _CLIENT_ID:
        return ""

    params = {
        "client_id": _CLIENT_ID,
        "redirect_uri": _REDIRECT_URI,
        "scope": "read:user repo",
        "state": state,
    }
    return f"https://github.com/login/oauth/authorize?{urllib.parse.urlencode(params)}"


def exchange_code_for_token(code: str) -> dict:
    """Exchange OAuth code for access token."""
    if not _CLIENT_ID or not _CLIENT_SECRET:
        return {"error": "GitHub OAuth not configured"}

    data = urllib.parse.urlencode({
        "client_id": _CLIENT_ID,
        "client_secret": _CLIENT_SECRET,
        "code": code,
        "redirect_uri": _REDIRECT_URI,
    }).encode()

    try:
        req = urllib.request.Request(
            "https://github.com/login/oauth/access_token",
            data=data,
            headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            if "access_token" in result:
                _tokens[result["access_token"]] = {
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "scope": result.get("scope", ""),
                }
                return {"access_token": result["access_token"], "scope": result.get("scope", "")}
            return {"error": result.get("error_description", "Token exchange failed")}
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        return {"error": f"Token exchange failed: {exc}"}


def fetch_user(token: str) -> dict:
    """Fetch authenticated user info from GitHub."""
    data = _fetch_github("https://api.github.com/user", token)
    if data:
        return {
            "login": data.get("login"),
            "name": data.get("name"),
            "avatar_url": data.get("avatar_url"),
            "public_repos": data.get("public_repos"),
        }
    return {}


def fetch_pr_timeline(
    token: str,
    owner: str,
    repo: str,
    limit: int = 30,
) -> list[dict]:
    """Fetch PR timeline for Slop Velocity analysis.

    Returns list of PR metadata with dates, review counts, and merge status.
    """
    url = f"https://api.github.com/repos/{owner}/{repo}/pulls?state=all&per_page={limit}"
    pulls = _fetch_github(url, token)
    if not pulls:
        return []

    timeline = []
    for pr in pulls:
        # Fetch review data
        reviews_url = pr.get("url", "") + "/reviews"
        reviews = _fetch_github(reviews_url, token) or []

        # Fetch commits count
        commits_url = pr.get("url", "") + "/commits"
        commits = _fetch_github(commits_url, token) or []

        timeline.append({
            "number": pr.get("number"),
            "title": pr.get("title"),
            "state": pr.get("state"),
            "merged": pr.get("merged_at") is not None,
            "created_at": pr.get("created_at"),
            "merged_at": pr.get("merged_at"),
            "author": pr.get("user", {}).get("login"),
            "review_count": len(reviews),
            "reviewers": [r.get("user", {}).get("login") for r in reviews if r.get("user")],
            "commit_count": len(commits) if isinstance(commits, list) else 0,
            "additions": pr.get("additions", 0),
            "deletions": pr.get("deletions", 0),
        })

    return timeline


def compute_slop_velocity(pr_timeline: list[dict], scored_prs: list[dict]) -> dict:
    """Compute Slop Velocity from real GitHub PR data + SlopGuard scores.

    Slop Velocity = rate of low-oversight PRs over time.
    A rising velocity suggests decreasing review quality.
    """
    if not pr_timeline or not scored_prs:
        return {
            "velocity_score": 0.5,
            "trend": "stable",
            "weekly_scores": [],
            "total_prs": 0,
        }

    # Map PR numbers to scores
    score_map = {sp.get("number"): sp.get("score", 50) for sp in scored_prs}

    # Group PRs by week
    weekly: dict[str, list[float]] = {}
    for pr in pr_timeline:
        created = pr.get("created_at", "")
        if not created:
            continue
        try:
            dt = datetime.fromisoformat(created.replace("Z", "+00:00"))
            week_key = f"W{dt.isocalendar()[1]}-{dt.year}"
            pr_number = pr.get("number")
            score = score_map.get(pr_number, 50)  # Default mid score if not scored
            weekly.setdefault(week_key, []).append(score)
        except (ValueError, TypeError):
            continue

    # Compute weekly averages
    weekly_scores = []
    for week_key in sorted(weekly.keys()):
        scores = weekly[week_key]
        weekly_scores.append({
            "week": week_key,
            "average_score": round(sum(scores) / len(scores), 1),
            "pr_count": len(scores),
        })

    # Compute velocity: change in average score over time
    if len(weekly_scores) >= 2:
        first_avg = weekly_scores[0]["average_score"]
        last_avg = weekly_scores[-1]["average_score"]
        velocity = last_avg - first_avg
        trend = "improving" if velocity > 5 else "degrading" if velocity < -5 else "stable"
    else:
        velocity = 0
        trend = "insufficient_data"

    return {
        "velocity_score": round(max(0, min(100, 50 + velocity)), 1),
        "trend": trend,
        "weekly_scores": weekly_scores[-8:],  # Last 8 weeks
        "total_prs": sum(ws["pr_count"] for ws in weekly_scores),
    }
