"""FAISS vector store adapter for large-scale batch clustering.

When faiss-cpu or faiss-gpu is installed, this module builds an IVF index
for fast nearest-neighbor search across thousands of text items. Falls back
to sklearn TF-IDF or trigram similarity when unavailable.

GPU Support:
    If faiss-gpu is installed and a CUDA device is available, the index is
    automatically moved to GPU for sub-millisecond search at scale.
    Install: pip install faiss-gpu

    The GPU index uses the same API — no code changes needed. The adapter
    auto-detects and uses GPU when available.
"""

from __future__ import annotations

import logging
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np

logger = logging.getLogger(__name__)

_gpu_resources = None
_gpu_enabled = False


def _get_gpu_resources():
    """Lazy-initialize FAISS GPU resources."""
    global _gpu_resources, _gpu_enabled
    if _gpu_resources is not None:
        return _gpu_resources, _gpu_enabled

    try:
        import faiss
        # Try to initialize GPU resources
        try:
            _gpu_resources = faiss.StandardGpuResources()
            _gpu_enabled = True
            logger.info("FAISS GPU resources initialized")
        except Exception:
            _gpu_resources = None
            _gpu_enabled = False
            logger.debug("FAISS GPU not available (faiss-gpu not installed or no CUDA device)")
    except ImportError:
        _gpu_resources = None
        _gpu_enabled = False

    return _gpu_resources, _gpu_enabled


def faiss_clusters(
    embeddings: "np.ndarray",
    texts: list[str],
    threshold: float = 0.60,
    nlist: int = 4,
) -> list[dict]:
    """Cluster items using FAISS IVF index for efficient similarity search.

    Args:
        embeddings: N×D numpy array of text embeddings.
        texts: Original text strings for reference.
        threshold: Cosine similarity threshold for clustering.
        nlist: Number of IVF clusters (auto-scaled for small datasets).

    Returns:
        List of cluster dicts with type, item_indexes, and similarity_score.
    """
    try:
        import faiss
        import numpy as np
    except ImportError:
        logger.debug("faiss-cpu not installed; caller should use fallback")
        return []

    n = len(embeddings)
    if n < 2:
        return []

    # Normalize embeddings for cosine similarity
    faiss.normalize_L2(embeddings)

    # Auto-scale nlist for small datasets
    actual_nlist = min(max(1, n // 4), nlist)
    if actual_nlist < 1:
        actual_nlist = 1

    # Build flat index for small datasets, IVF for larger ones
    dim = embeddings.shape[1]
    use_gpu = n >= 1000  # Use GPU only for large datasets (1000+ items)

    if n < 100:
        base_index = faiss.IndexFlatIP(dim)
    else:
        quantizer = faiss.IndexFlatIP(dim)
        base_index = faiss.IndexIVFFlat(quantizer, dim, actual_nlist, faiss.METRIC_INNER_PRODUCT)
        base_index.train(embeddings)

    # Wrap with GPU index if available
    if use_gpu:
        gpu_res, gpu_available = _get_gpu_resources()
        if gpu_available and gpu_res is not None:
            index = faiss.index_cpu_to_gpu(gpu_res, 0, base_index)
            logger.debug("FAISS index moved to GPU for %d items", n)
        else:
            index = base_index
    else:
        index = base_index

    index.add(embeddings)

    # Search: find neighbors above threshold for each item
    k = min(n, 16)  # search top-k neighbors
    scores, neighbors = index.search(embeddings, k)

    used: set[int] = set()
    clusters = []

    for i in range(n):
        if i in used:
            continue
        group = [i]
        sims = []
        for j_idx in range(1, k):
            j = neighbors[i, j_idx]
            s = scores[i, j_idx]
            if j < n and s >= threshold and j not in used:
                group.append(int(j))
                sims.append(float(s))

        if len(group) > 1:
            used.update(group)
            avg_sim = sum(sims) / len(sims) if sims else threshold
            clusters.append(
                {
                    "type": "faiss_similarity",
                    "item_indexes": group,
                    "similarity_score": round(avg_sim, 3),
                    "reason": "Items share high embedding cosine similarity via FAISS IVF index.",
                }
            )

    return clusters


def faiss_search_similar(
    embeddings: "np.ndarray",
    query_embedding: "np.ndarray",
    top_k: int = 5,
) -> list[tuple[int, float]]:
    """Search for the most similar items to a query embedding.

    Returns list of (index, similarity_score).
    Uses GPU if available for large embedding sets.
    """
    try:
        import faiss
        import numpy as np
    except ImportError:
        return []

    faiss.normalize_L2(query_embedding)
    faiss.normalize_L2(embeddings)

    dim = embeddings.shape[1]
    n = len(embeddings)
    base_index = faiss.IndexFlatIP(dim)
    base_index.add(embeddings)

    # Use GPU for large embedding sets
    if n >= 1000:
        gpu_res, gpu_available = _get_gpu_resources()
        if gpu_available and gpu_res is not None:
            index = faiss.index_cpu_to_gpu(gpu_res, 0, base_index)
            logger.debug("FAISS search on GPU for %d embeddings", n)
        else:
            index = base_index
    else:
        index = base_index

    scores, indices = index.search(query_embedding.reshape(1, -1), top_k)

    results = []
    for i, idx in enumerate(indices[0]):
        if idx < len(embeddings):
            results.append((int(idx), float(scores[0][i])))
    return results
