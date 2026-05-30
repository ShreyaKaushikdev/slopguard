"""NetworkX graph-based documentation circularity detection.

Builds a directed graph of sentence-to-sentence references and detects
cycles that indicate circular explanations (A refers to B, B refers to A).
Falls back to sliding-window entity overlap when networkx is unavailable.
"""

from __future__ import annotations

import logging
import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)


def _extract_entities(sentence: str) -> set[str]:
    """Extract content entities (nouns, technical terms) from a sentence."""
    # Filter to tokens > 3 chars, excluding common stop words
    stop = {
        "this", "that", "these", "those", "they", "them", "their", "there",
        "which", "what", "when", "where", "who", "how", "why", "the", "and",
        "but", "for", "not", "are", "was", "were", "been", "being", "have",
        "has", "had", "does", "did", "will", "would", "could", "should",
        "may", "might", "must", "shall", "can", "need", "dare", "ought",
        "used", "from", "into", "like", "near", "onto", "over", "some",
        "than", "through", "to", "toward", "until", "upon", "with", "within",
        "about", "above", "below", "between", "under", "again", "further",
        "once", "here", "also", "very", "just", "only", "even", "still",
        "own", "same", "so", "than", "too", "most", "other", "each", "few",
        "more", "both", "such", "because", "while", "although", "though",
        "since", "unless", "until", "whether", "however", "therefore",
        "thus", "hence", "then", "else", "otherwise", "meanwhile",
    }
    tokens = re.findall(r"[A-Za-z][A-Za-z0-9_'-]{3,}", sentence.lower())
    return {t for t in tokens if t not in stop}


def _build_reference_graph(sentences: list[str], entity_sets: list[set[str]]) -> "list[tuple[int, int]] | None":
    """Build directed edges where sentence i references entities introduced in sentence j."""
    try:
        import networkx as nx
    except ImportError:
        logger.debug("networkx not installed; cannot build reference graph")
        return None

    n = len(sentences)
    if n < 2:
        return []

    G = nx.DiGraph()
    for i in range(n):
        G.add_node(i)

    # Track which entities are first introduced in which sentence
    entity_first_seen: dict[str, int] = {}
    for i, entities in enumerate(entity_sets):
        for entity in entities:
            if entity not in entity_first_seen:
                entity_first_seen[entity] = i

    # Add edges: if sentence i uses an entity first seen in sentence j, edge j -> i
    for i, entities in enumerate(entity_sets):
        for entity in entities:
            first_idx = entity_first_seen.get(entity)
            if first_idx is not None and first_idx != i:
                G.add_edge(first_idx, i, entity=entity)

    # Find all simple cycles
    cycles = list(nx.simple_cycles(G))
    return cycles


def circularity_graph_score(text: str) -> tuple[float, list[dict]]:
    """Detect circular explanations using NetworkX graph cycle detection.

    Returns (score, details) where score ∈ [0, 1] (higher = less circular).
    Falls back to 0.5 (neutral) and empty details when networkx is unavailable.
    """
    try:
        import networkx as nx
    except ImportError:
        return 0.5, [{"reason": "networkx not installed; cannot perform graph analysis"}]

    from slopguard.detectors.universal import split_sentences

    sentences = split_sentences(text)
    if len(sentences) < 3:
        return 1.0, []

    entity_sets = [_extract_entities(s) for s in sentences]

    # Build reference graph
    G = nx.DiGraph()
    for i in range(len(sentences)):
        G.add_node(i)

    entity_first_seen: dict[str, int] = {}
    for i, entities in enumerate(entity_sets):
        for entity in entities:
            if entity not in entity_first_seen:
                entity_first_seen[entity] = i

    for i, entities in enumerate(entity_sets):
        for entity in entities:
            first_idx = entity_first_seen.get(entity)
            if first_idx is not None and first_idx != i:
                if not G.has_edge(first_idx, i):
                    G.add_edge(first_idx, i)

    # Find cycles
    cycles = list(nx.simple_cycles(G))
    circular_windows = len(cycles)
    total_sentences = len(sentences)

    # Also compute the circularity ratio from the original sliding window method
    # as a complementary signal
    from slopguard.detectors.domains import overlap_score

    circular_pairs = 0
    total_pairs = 0
    for i in range(len(sentences) - 2):
        for j in range(i + 2, min(i + 5, len(sentences))):
            total_pairs += 1
            if overlap_score(sentences[i], sentences[j]) > 0.5:
                circular_pairs += 1

    circular_ratio = circular_pairs / max(total_pairs, 1)

    # Score: penalize for both graph cycles and high similarity pairs
    cycle_penalty = min(circular_windows * 0.08, 0.5)
    similarity_penalty = circular_ratio * 0.3
    score = max(0.0, min(1.0, 1.0 - cycle_penalty - similarity_penalty))

    details = []
    if cycles:
        for cycle in cycles[:5]:  # Limit detail output
            cycle_sentences = [sentences[i][:80] + "..." for i in cycle]
            details.append({
                "cycle_length": len(cycle),
                "sentences": cycle_sentences,
            })

    return round(score, 3), details
