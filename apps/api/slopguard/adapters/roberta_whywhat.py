"""RoBERTa WHY vs WHAT classifier adapter.

When transformers is installed, this module uses a lightweight distilled
RoBERTa model to classify sentences as reasoning (WHY) or declarative (WHAT).
Falls back to cue-based marker counting when unavailable.

Fine-tuning:
    Run slopguard/adapters/finetune_roberta.py to train on a labeled dataset.
    The fine-tuned model will be loaded automatically if present.
"""

from __future__ import annotations

import logging
import os
import re
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np

logger = logging.getLogger(__name__)

_pipeline = None
_finetuned_model = None

_FINETUNED_PATHS = [
    "models/whywhat-roberta",
    os.path.join(os.path.dirname(__file__), "..", "..", "..", "models", "whywhat-roberta"),
]


def _find_finetuned_model() -> str | None:
    """Look for a fine-tuned WHY/WHAT model."""
    for path in _FINETUNED_PATHS:
        if Path(path).exists() and (Path(path) / "config.json").exists():
            return path
    return None


def _load_pipeline() -> None:
    """Lazy-load the transformers pipeline."""
    global _pipeline, _finetuned_model
    if _pipeline is not None:
        return

    # Check for fine-tuned model first
    _finetuned_model = _find_finetuned_model()
    model_name = _finetuned_model or "facebook/bart-large-mnli"
    is_zero_shot = _finetuned_model is None

    try:
        from transformers import pipeline

        if is_zero_shot:
            _pipeline = pipeline(
                "zero-shot-classification",
                model=model_name,
                device=-1,  # CPU
            )
            logger.info("RoBERTa zero-shot pipeline loaded (facebook/bart-large-mnli)")
        else:
            _pipeline = pipeline(
                "text-classification",
                model=model_name,
                device=-1,
                return_all_scores=True,
            )
            logger.info("RoBERTa fine-tuned pipeline loaded from %s", _finetuned_model)
    except ImportError:
        _pipeline = None
        logger.debug("transformers not installed; using cue-based WHY/WHAT fallback")
    except Exception as exc:
        _pipeline = None
        logger.warning("Failed to load RoBERTa pipeline: %s", exc)


def classify_sentence_roberta(sentence: str) -> tuple[str, float]:
    """Classify a single sentence as 'why' or 'what' using RoBERTa.

    Uses fine-tuned model if available, otherwise zero-shot BART.
    Returns (label, confidence) where label is 'why' or 'what'.
    Falls back to ('neutral', 0.5) when unavailable.
    """
    _load_pipeline()
    if _pipeline is None:
        return "neutral", 0.5

    try:
        if _finetuned_model:
            # Fine-tuned model: direct classification
            result = _pipeline(sentence, truncation=True)
            # result is [[{"label": "LABEL_0", "score": 0.9}, ...]]
            scores = result[0] if isinstance(result[0], list) else result
            top = max(scores, key=lambda x: x["score"])
            label_id = int(top["label"].split("_")[1]) if "LABEL_" in top["label"] else 0
            label_map = {0: "why", 1: "what", 2: "neutral"}
            return label_map.get(label_id, "neutral"), top["score"]
        else:
            # Zero-shot classification
            candidate_labels = [
                "explains reasoning or cause",
                "describes action or fact",
                "neutral statement",
            ]
            result = _pipeline(sentence, candidate_labels, truncation=True)
            top_label = result["labels"][0]
            top_score = result["scores"][0]
            if "reasoning" in top_label or "cause" in top_label:
                return "why", top_score
            elif "action" in top_label or "fact" in top_label:
                return "what", top_score
            return "neutral", 0.5
    except Exception as exc:
        logger.warning("RoBERTa classification failed: %s", exc)
        return "neutral", 0.5


def classify_sentences_roberta(sentences: list[str]) -> list[tuple[str, float]]:
    """Classify multiple sentences. Returns list of (label, confidence)."""
    return [classify_sentence_roberta(s) for s in sentences]


def why_what_roberta_ratio(text: str) -> float:
    """Return WHY vs WHAT ratio using RoBERTa classification.

    Returns a float in [0, 1] where higher means more reasoning (WHY).
    Falls back to cue-based ratio when RoBERTa is unavailable.
    """
    _load_pipeline()

    # Split into sentences
    sentences = re.split(r"(?<=[.!?])\s+", text.strip())
    sentences = [s.strip() for s in sentences if s.strip() and len(s.split()) > 2]

    if not sentences:
        return 0.5

    if _pipeline is None:
        # Fall back to cue-based counting
        from slopguard.detectors.universal import WHY_MARKERS, WHAT_MARKERS
        lower = text.lower()
        why_hits = sum(1 for m in WHY_MARKERS if m in lower)
        what_hits = sum(1 for m in WHAT_MARKERS if m in lower)
        total = why_hits + what_hits
        return why_hits / total if total > 0 else 0.5

    # Use RoBERTa
    why_count = 0
    what_count = 0
    for sentence in sentences[:20]:  # Limit to first 20 for speed
        label, _ = classify_sentence_roberta(sentence)
        if label == "why":
            why_count += 1
        elif label == "what":
            what_count += 1

    total = why_count + what_count
    return why_count / total if total > 0 else 0.5
