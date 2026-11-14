"""Local text embeddings. Production: fastembed multilingual-e5-small. Tests: FakeEmbedder (no download)."""
from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

from backend.app.config import settings
from backend.app.models import EMBEDDING_DIM


class Embedder(Protocol):
    def embed_passages(self, texts: list[str]) -> list[list[float]]: ...
    def embed_query(self, text: str) -> list[float]: ...


class FastEmbedEmbedder:
    """e5 models expect 'query: ' / 'passage: ' prefixes; added here, not by fastembed."""

    def __init__(self, model_name: str = settings.embedding_model, cache_dir: str = settings.fastembed_cache):
        from fastembed import TextEmbedding
        from fastembed.common.model_description import ModelSource, PoolingType

        if model_name not in {m["model"] for m in TextEmbedding.list_supported_models()}:
            TextEmbedding.add_custom_model(
                model=model_name, pooling=PoolingType.MEAN, normalization=True,
                sources=ModelSource(hf=model_name), dim=EMBEDDING_DIM, model_file="onnx/model.onnx",
            )
        self._model = TextEmbedding(model_name, cache_dir=cache_dir)

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        return [v.tolist() for v in self._model.embed([f"passage: {t}" for t in texts])]

    def embed_query(self, text: str) -> list[float]:
        return next(iter(self._model.embed([f"query: {text}"]))).tolist()


class FakeEmbedder:
    """Deterministic hashed bag-of-words; shared words give high cosine, unrelated text ~0."""

    def _vec(self, text: str) -> list[float]:
        v = [0.0] * EMBEDDING_DIM
        for tok in re.findall(r"\w+", text.lower()):
            if len(tok) < 3:
                continue
            v[int(hashlib.md5(tok.encode()).hexdigest(), 16) % EMBEDDING_DIM] += 1.0
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        return [x / norm for x in v]

    def embed_passages(self, texts: list[str]) -> list[list[float]]:
        return [self._vec(t) for t in texts]

    def embed_query(self, text: str) -> list[float]:
        return self._vec(text)


_embedder: Embedder | None = None


def set_embedder(embedder: Embedder | None) -> None:
    global _embedder
    _embedder = embedder


def get_embedder() -> Embedder:
    global _embedder
    if _embedder is None:
        _embedder = FastEmbedEmbedder()
    return _embedder
