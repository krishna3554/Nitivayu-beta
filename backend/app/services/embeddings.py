"""Process-level MiniLM embedding loader for the Temporal worker.

The repository documents ``paraphrase-multilingual-MiniLM-L12-v2`` as the
384-dimensional local embedding model. The model is loaded lazily once per
worker process and reused across activities; it is never reloaded per call.
``SENTENCE_TRANSFORMERS_HOME`` is honored by the underlying library and maps
to the existing ``model_cache`` Docker volume.
"""

from __future__ import annotations

import math
import threading

from app.config import get_settings

EMBEDDING_MODEL = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
EMBEDDING_DIMENSIONS = 384

_lock = threading.Lock()
_model = None
_model_name: str | None = None


def get_embedding_model():
    """Return the cached embedding model, loading it once per worker process."""
    global _model, _model_name
    settings = get_settings()
    model_name = getattr(settings, "EMBEDDING_MODEL", EMBEDDING_MODEL) or EMBEDDING_MODEL
    if _model is not None and _model_name == model_name:
        return _model
    with _lock:
        if _model is not None and _model_name == model_name:
            return _model
        try:
            from sentence_transformers import SentenceTransformer
        except ImportError as exc:
            raise RuntimeError(
                "sentence-transformers is required by the worker image to generate embeddings"
            ) from exc
        model = SentenceTransformer(model_name)
        get_dimension = getattr(model, "get_embedding_dimension", None) or getattr(
            model, "get_sentence_embedding_dimension", None
        )
        dimensions = int(get_dimension() or 0) if get_dimension else 0
        if dimensions != EMBEDDING_DIMENSIONS:
            raise RuntimeError(
                f"Embedding model {model_name} has {dimensions} dimensions; "
                f"the database schema requires {EMBEDDING_DIMENSIONS}"
            )
        _model = model
        _model_name = model_name
        return _model


def embed_text(text: str) -> list[float]:
    """Generate one normalized 384-dimensional embedding."""
    cleaned = " ".join((text or "").split())
    if not cleaned:
        raise ValueError("Cannot embed blank text")
    vector = get_embedding_model().encode(cleaned, normalize_embeddings=True)
    values = [float(value) for value in list(vector)]
    if len(values) != EMBEDDING_DIMENSIONS or any(not math.isfinite(value) for value in values):
        raise ValueError("Embedding model returned an invalid vector")
    return values
