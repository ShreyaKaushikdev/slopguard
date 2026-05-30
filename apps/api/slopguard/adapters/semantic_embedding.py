"""Semantic embedding adapter using sentence-transformers.

When sentence-transformers is installed, this module provides deep
semantic similarity scores via cosine distance of sentence embeddings.
Falls back to trigram Jensen-Shannon divergence when unavailable.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np

logger = logging.getLogger(__name__)

_model = None
_embedding_dim = 0


def _load_model(model_name: str = "all-MiniLM-L6-v2") -> None:
    """Lazy-load the sentence-transformers model."""
    global _model, _embedding_dim
    if _model is not None:
        return
    try:
        from sentence_transformers import SentenceTransformer
        _model = SentenceTransformer(model_name)
        _embedding_dim = _model.get_sentence_embedding_dimension() or 384
        logger.info("sentence-transformers loaded: %s", model_name)
    except ImportError:
        _model = None
        logger.debug("sentence-transformers not installed; using trigram fallback")


def encode(texts: list[str]) -> "np.ndarray | None":
    """Return embedding matrix for a list of texts, or None if unavailable."""
    _load_model()
    if _model is None:
        return None
    return _model.encode(texts, convert_to_numpy=True, show_progress_bar=False)


def semantic_embedding_uniqueness(text: str) -> float:
    """Score how semantically unique the text is using embeddings.

    Higher = more unique / less slop-like.
    Uses embedding distance from a known AI-slop centroid.
    Falls back to 0.5 (neutral) when embeddings unavailable.
    """
    _load_model()
    if _model is None:
        return 0.5  # fallback to neutral

    try:
        embedding = _model.encode(text, convert_to_numpy=True)
        # Compare against a synthetic "slop centroid" built from common AI phrases
        slop_phrases = [
            "This comprehensive guide explores the various aspects of modern technology.",
            "In today's digital landscape, it is important to leverage best practices.",
            "This article delves into the transformative power of innovative solutions.",
            "Unlock the full potential of your workflow with this seamless experience.",
        ]
        slop_embedding = _model.encode(slop_phrases, convert_to_numpy=True)
        slop_centroid = slop_embedding.mean(axis=0)

        # Cosine similarity to slop centroid
        import numpy as np
        dot = float(np.dot(embedding, slop_centroid))
        norm_a = float(np.linalg.norm(embedding))
        norm_b = float(np.linalg.norm(slop_centroid))
        if norm_a == 0 or norm_b == 0:
            return 0.5
        cos_sim = dot / (norm_a * norm_b)
        # Invert: lower similarity to slop = higher score
        return max(0.0, min(1.0, 1.0 - cos_sim))
    except Exception as exc:
        logger.warning("sentence-transformers scoring failed: %s", exc)
        return 0.5


def embedding_similarity_matrix(texts: list[str]) -> "np.ndarray | None":
    """Return cosine similarity matrix for a list of texts, or None."""
    _load_model()
    if _model is None:
        return None
    try:
        import numpy as np
        from sklearn.metrics.pairwise import cosine_similarity
        embeddings = _model.encode(texts, convert_to_numpy=True, show_progress_bar=False)
        return cosine_similarity(embeddings)
    except Exception as exc:
        logger.warning("embedding similarity matrix failed: %s", exc)
        return None
