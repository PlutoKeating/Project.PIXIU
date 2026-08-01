"""MockEmbedding — deterministic / random fixed-dim vectors for offline V0.1."""

from __future__ import annotations

import hashlib
import os
import random
from typing import Protocol, runtime_checkable


@runtime_checkable
class TextEmbedder(Protocol):
    def embed(self, text: str) -> list[float]: ...


DEFAULT_DIM = 256


class MockEmbedding:
    """Return a fixed-dimension vector. Deterministic by default (hash-based)."""

    def __init__(self, dim: int = DEFAULT_DIM, *, deterministic: bool = True) -> None:
        self.dim = dim
        self.deterministic = deterministic

    def embed(self, text: str) -> list[float]:
        if self.deterministic:
            digest = hashlib.sha256(text.encode("utf-8")).digest()
            rng = random.Random(int.from_bytes(digest[:8], "big"))
            return [rng.uniform(-1.0, 1.0) for _ in range(self.dim)]
        return [random.random() for _ in range(self.dim)]


class KylinTextEmbedding:
    """Placeholder for real Kylin coreai/embedding binding.

    V0.1 falls back to MockEmbedding unless PIXIU_EMBEDDING=kylin and the
    native extension is available (not required for this release).
    """

    def __init__(self) -> None:
        self._fallback = MockEmbedding()

    def embed(self, text: str) -> list[float]:
        # Real C API binding lands in a later version.
        return self._fallback.embed(text)


def get_embedder() -> TextEmbedder:
    backend = os.environ.get("PIXIU_EMBEDDING", "mock").lower()
    if backend == "kylin":
        return KylinTextEmbedding()
    return MockEmbedding()
