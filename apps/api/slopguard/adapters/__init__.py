"""Production adapters — optional model-backed upgrades.

All adapters gracefully fall back to deterministic implementations when
their dependencies are not installed. Import and use them directly; they
handle their own availability checks.
"""

# Semantic embedding (sentence-transformers)
from slopguard.adapters.semantic_embedding import (
    encode as embedding_encode,
    embedding_similarity_matrix,
    semantic_embedding_uniqueness,
)

# RoBERTa WHY/WHAT classifier (transformers)
from slopguard.adapters.roberta_whywhat import (
    classify_sentence_roberta,
    classify_sentences_roberta,
    why_what_roberta_ratio,
)

# FAISS vector store (faiss-cpu)
from slopguard.adapters.faiss_clustering import faiss_clusters, faiss_search_similar

# NetworkX graph circularity (networkx)
from slopguard.adapters.networkx_circularity import circularity_graph_score

# Tree-sitter AST parsing (tree-sitter)
from slopguard.adapters.treesitter_comments import code_comment_intelligence_ast

# Expanded citation verification (CrossRef + Semantic Scholar + PubMed)
from slopguard.adapters.citation_verification import (
    verify_citation,
    verify_citations_batch,
    verify_crossref,
    verify_pubmed,
    verify_semantic_scholar,
)

# Supabase telemetry (supabase-py)
from slopguard.adapters.supabase_telemetry import (
    get_user_summary,
    insert_feedback,
    insert_score_event,
    is_enabled as supabase_is_enabled,
    upsert_user_profile,
)

# GitHub OAuth (httpx / stdlib)
from slopguard.adapters.github_oauth import (
    compute_slop_velocity,
    exchange_code_for_token,
    fetch_pr_timeline,
    fetch_user,
    get_auth_url,
)

# Adaptive baselines (in-memory, Supabase-ready)
from slopguard.adapters.baselines import (
    clear_all as baselines_clear_all,
    get_relative_score,
    get_repo_profile,
    update_baseline,
)

# Live Slop Ticker
from slopguard.adapters.ticker import (
    get_ticker_snapshot,
    get_ticker_stream_instance,
    refresh_and_publish,
)

__all__ = [
    # Semantic embedding
    "embedding_encode",
    "embedding_similarity_matrix",
    "semantic_embedding_uniqueness",
    # RoBERTa
    "classify_sentence_roberta",
    "classify_sentences_roberta",
    "why_what_roberta_ratio",
    # FAISS
    "faiss_clusters",
    "faiss_search_similar",
    # NetworkX
    "circularity_graph_score",
    # Tree-sitter
    "code_comment_intelligence_ast",
    # Citations
    "verify_citation",
    "verify_citations_batch",
    "verify_crossref",
    "verify_pubmed",
    "verify_semantic_scholar",
    # Supabase
    "get_user_summary",
    "insert_feedback",
    "insert_score_event",
    "supabase_is_enabled",
    "upsert_user_profile",
    # GitHub
    "compute_slop_velocity",
    "exchange_code_for_token",
    "fetch_pr_timeline",
    "fetch_user",
    "get_auth_url",
    # Baselines
    "baselines_clear_all",
    "get_relative_score",
    "get_repo_profile",
    "update_baseline",
    # Ticker
    "get_ticker_snapshot",
    "get_ticker_stream_instance",
    "refresh_and_publish",
]
