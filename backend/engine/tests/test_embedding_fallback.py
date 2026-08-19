"""Kylin-first embedding selection and portable Debian fallback."""

from __future__ import annotations

import pytest

from backend.engine.kylin.embedding import (
    KylinSDKUnavailableError,
    PortableTextEmbedding,
    get_embedder,
)


def test_auto_embedding_falls_back_without_kylin_sdk() -> None:
    assert isinstance(get_embedder("auto"), PortableTextEmbedding)


def test_strict_kylin_embedding_fails_without_sdk() -> None:
    with pytest.raises(KylinSDKUnavailableError):
        get_embedder("kylin")


def test_portable_embedding_is_stable_and_normalized() -> None:
    embedder = PortableTextEmbedding(dim=64)
    first = embedder.embed("麒麟 Debian compatibility")
    second = embedder.embed("麒麟 Debian compatibility")

    assert first == second
    assert len(first) == 64
    assert sum(value * value for value in first) == pytest.approx(1.0)


def test_portable_embedding_preserves_lexical_similarity() -> None:
    embedder = PortableTextEmbedding(dim=256)
    base = embedder.embed("四月份家庭电费账单")
    related = embedder.embed("四月份家庭燃气账单")
    unrelated = embedder.embed("爵士乐播放列表")

    def dot(left: list[float], right: list[float]) -> float:
        return sum(a * b for a, b in zip(left, right))

    assert dot(base, related) > dot(base, unrelated)
