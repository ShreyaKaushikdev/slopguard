"""Expanded citation verification: CrossRef + Semantic Scholar + PubMed.

Verifies citations against three scholarly APIs. Returns structured results
with source attribution and confidence levels.
"""

from __future__ import annotations

import json
import logging
import re
import urllib.error
import urllib.request
from typing import Literal

logger = logging.getLogger(__name__)

CitationStatus = Literal["verified", "likely_real", "needs_review", "not_found"]


def _fetch_json(url: str, timeout: int = 10) -> dict | None:
    """Fetch JSON from a URL, returning None on failure."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "SlopGuard-Citation/0.1"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8", errors="replace"))
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError) as exc:
        logger.debug("Citation API fetch failed for %s: %s", url, exc)
        return None


def _extract_doi(citation: str) -> str | None:
    """Extract DOI from citation text."""
    match = re.search(r"10\.\d{4,9}/[-._;()/:A-Za-z0-9]+", citation)
    return match.group(0) if match else None


def _extract_pmid(citation: str) -> str | None:
    """Extract PubMed ID from citation text."""
    match = re.search(r"PMID[:\s]*(\d{5,9})", citation, re.I)
    if match:
        return match.group(1)
    # Also try standalone 7-9 digit numbers that look like PMIDs
    match = re.search(r"\b(\d{7,9})\b", citation)
    if match and "doi" not in citation.lower():
        return match.group(1)
    return None


def _extract_title(citation: str) -> str | None:
    """Extract a probable title from citation text."""
    # Try quoted title
    match = re.search(r'"([^"]{10,})"', citation)
    if match:
        return match.group(1)
    # Try title case sequence
    match = re.search(r"([A-Z][A-Za-z\s,':\-]{20,80})", citation)
    if match:
        return match.group(1).strip()
    return None


def verify_crossref(doi: str) -> dict | None:
    """Verify a DOI through CrossRef API."""
    data = _fetch_json(f"https://api.crossref.org/works/{doi}")
    if data and data.get("status") == "ok":
        message = data.get("message", {})
        return {
            "source": "crossref",
            "status": "verified",
            "title": message.get("title", [""])[0],
            "authors": message.get("author", []),
            "year": message.get("published-print", {}).get("date-parts", [[0]])[0][0],
            "doi": doi,
        }
    return None


def verify_semantic_scholar(citation: str, doi: str | None = None) -> dict | None:
    """Verify a citation through Semantic Scholar API."""
    # Try by DOI first
    if doi:
        data = _fetch_json(f"https://api.semanticscholar.org/graph/v1/paper/DOI:{doi}?fields=title,authors,year,citationCount")
        if data and data.get("title"):
            return {
                "source": "semantic_scholar",
                "status": "verified",
                "title": data["title"],
                "authors": data.get("authors", []),
                "year": data.get("year"),
                "citation_count": data.get("citationCount"),
                "doi": doi,
            }

    # Try by title search
    title = _extract_title(citation)
    if title:
        encoded = urllib.parse.quote(title[:100])
        data = _fetch_json(f"https://api.semanticscholar.org/graph/v1/paper/search?query={encoded}&limit=1&fields=title,authors,year,citationCount")
        if data and data.get("data"):
            paper = data["data"][0]
            return {
                "source": "semantic_scholar",
                "status": "verified",
                "title": paper.get("title"),
                "authors": paper.get("authors", []),
                "year": paper.get("year"),
                "citation_count": paper.get("citationCount"),
            }

    return None


def verify_pubmed(citation: str, pmid: str | None = None) -> dict | None:
    """Verify a citation through PubMed/E-utilities API."""
    if pmid:
        url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi?db=pubmed&id={pmid}&retmode=json"
        data = _fetch_json(url)
        if data and data.get("result"):
            # Get the first result key (not 'uids')
            uids = data["result"].get("uids", [])
            if uids:
                article = data["result"].get(uids[0], {})
                return {
                    "source": "pubmed",
                    "status": "verified",
                    "title": article.get("title", ""),
                    "authors": article.get("authors", []),
                    "year": article.get("pubdate", "")[:4],
                    "pmid": pmid,
                }

    # Try searching by title
    title = _extract_title(citation)
    if title:
        encoded = urllib.parse.quote(title[:50])
        url = f"https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi?db=pubmed&term={encoded}&retmode=json"
        data = _fetch_json(url)
        if data and data.get("esearchresult", {}).get("idlist"):
            pmid_found = data["esearchresult"]["idlist"][0]
            return {
                "source": "pubmed",
                "status": "likely_real",
                "pmid": pmid_found,
                "note": "Found via title search; verify manually.",
            }

    return None


def verify_citation(citation: str) -> dict:
    """Verify a citation against CrossRef, Semantic Scholar, and PubMed.

    Returns structured result with source, status, and metadata.
    """
    doi = _extract_doi(citation)
    pmid = _extract_pmid(citation)

    # Try CrossRef
    if doi:
        result = verify_crossref(doi)
        if result:
            return result

    # Try Semantic Scholar
    ss_result = verify_semantic_scholar(citation, doi)
    if ss_result:
        return ss_result

    # Try PubMed
    pm_result = verify_pubmed(citation, pmid)
    if pm_result:
        return pm_result

    # Fallback: local shape check
    known_markers = ("doi:", "arxiv", "nature", "science", "acm", "ieee", "pubmed", "pmid")
    has_marker = any(marker in citation.lower() for marker in known_markers)

    return {
        "source": "local_shape_check",
        "status": "likely_real" if has_marker else "needs_review",
        "citation": citation[:120],
        "reason": "Not found in CrossRef, Semantic Scholar, or PubMed. "
                  + ("Contains scholarly marker." if has_marker else "No recognizable source marker."),
    }


def verify_citations_batch(citations: list[str]) -> list[dict]:
    """Verify multiple citations, returning results in order."""
    return [verify_citation(c) for c in citations]
