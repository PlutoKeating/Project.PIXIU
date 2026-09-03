"""Kylin-first embedding selection and portable Debian fallback."""

from __future__ import annotations

import sys
from types import ModuleType

import pytest

import backend.engine.kylin.embedding as embedding_module
from backend.engine.kylin.embedding import (
    KylinSDKUnavailableError,
    KylinTextEmbedding,
    PortableTextEmbedding,
    get_embedder,
)


class _FakeNativeEmbedding:
    vector = [0.25, 0.5]

    def __init__(self, model_name: str) -> None:
        self.selected = model_name or "system-text-model"

    def embed(self, text: str) -> list[float]:
        return list(type(self).vector)

    def dim(self) -> int:
        return 2

    def model_name(self) -> str:
        return self.selected


def _install_fake_native(monkeypatch) -> None:
    module = ModuleType("backend.engine.kylin._kylin_text_embedding")
    module.KylinTextEmbedding = _FakeNativeEmbedding  # type: ignore[attr-defined]
    monkeypatch.setitem(
        sys.modules, "backend.engine.kylin._kylin_text_embedding", module
    )


def _sdk_unavailable():
    raise KylinSDKUnavailableError("simulated missing SDK")


def test_auto_embedding_falls_back_without_kylin_sdk(monkeypatch) -> None:
    monkeypatch.setattr(embedding_module, "_load_native", _sdk_unavailable)

    assert isinstance(get_embedder("auto"), PortableTextEmbedding)


def test_strict_kylin_embedding_fails_without_sdk(monkeypatch) -> None:
    monkeypatch.setattr(embedding_module, "_load_native", _sdk_unavailable)

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


def test_kylin_embedding_reports_effective_model_and_runtime(monkeypatch) -> None:
    _install_fake_native(monkeypatch)

    embedder = KylinTextEmbedding()

    assert embedder.runtime == "kylin"
    assert embedder.model_name == "system-text-model"
    assert embedder.dim == 2
    assert embedder.embed("hello") == [0.25, 0.5]


def test_kylin_embedding_rejects_runtime_dimension_drift(monkeypatch) -> None:
    _install_fake_native(monkeypatch)
    _FakeNativeEmbedding.vector = [0.25]
    embedder = KylinTextEmbedding()

    try:
        with pytest.raises(RuntimeError, match="dimension mismatch"):
            embedder.embed("hello")
    finally:
        _FakeNativeEmbedding.vector = [0.25, 0.5]
