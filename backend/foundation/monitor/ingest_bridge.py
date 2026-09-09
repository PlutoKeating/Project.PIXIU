"""Authorized directory capture with model-based image/PDF understanding.

Text capture currently uses the existing memory pipeline. Document decoding and
controlled dreaming will replace direct ingestion under the approved harness plan.
OCR is not used for knowledge extraction.
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from ..core.logger import get_logger
from ..core.models import FileCaptureSource, validate_scope

log = get_logger(__name__)

#: 文本直读后缀（≤ max_text_bytes）。
TEXT_SUFFIXES = frozenset({".txt", ".md", ".csv"})

#: 图片后缀（由当前模型理解）。
IMAGE_SUFFIXES = frozenset({".png", ".jpg", ".jpeg", ".bmp", ".webp"})

#: 事件状态（对齐 frontend/docs/MONITOR_API_REQUIREMENTS.md §2 契约）。
STATUS_INGESTED = "ingested"
STATUS_SENSITIVE_QUARANTINED = "sensitive_quarantined"
STATUS_IGNORED = "ignored"


@dataclass(frozen=True)
class CaptureResult:
    """单文件捕获结果（on_capture 事件载荷）。"""

    status: str
    summary: str
    evidence_id: str | None = None
    knowledge_id: str | None = None
    ts: int = 0


class OcrAdapter(Protocol):
    """OCR 适配器接口（对齐 engine/kylin/ocr.py: KylinOcr/StructuredTextOcr）。"""

    def recognize(self, image_path: str | Path, nums: int = 4) -> list[str]: ...


def _read_text(path: str) -> str | None:
    """读取文本文件内容（UTF-8；失败时记日志并返回 None，不中断监视）。"""
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except OSError:
        log.warning("cannot read text file %s", path, exc_info=True)
        return None


class IngestBridge:
    """文件 → evidence/knowledge 桥接。

    用法：
        bridge = IngestBridge(ingestion, knowledge, security=security, ocr=ocr)
        result = await bridge.capture("/path/to/file.png")
    """

    def __init__(
        self,
        ingestion: Any,
        knowledge: Any,
        *,
        security: Any | None = None,
        ocr: OcrAdapter | None = None,
        media: Any | None = None,
        scope: str = "user:local",
        max_text_bytes: int = 1024 * 1024,
        source_type: str = "MANUAL_CONFIG",
    ) -> None:
        #: 复用 api 层指定的同进程 pipeline 服务（ingest / knowledge / security）。
        self._ingestion = ingestion
        self._knowledge = knowledge
        #: security 可选：提供时按既有 detector 判定敏感度（sensitive_quarantined）。
        self._security = security
        self._ocr = ocr  # reserved for sensitivity annotations; never knowledge extraction
        self._media = media
        #: 捕获落库 scope —— 监视写入默认本机 user:*，敏感条目绝不入 shared:*。
        self._scope = validate_scope(scope)
        if not self._scope.startswith("user:"):
            raise ValueError("directory capture requires a private user:* scope")
        self._max_text_bytes = max_text_bytes
        #: 入库 source_type（对齐计划：目录捕获组装 MANUAL 风格证据）。
        self._source_type = source_type

    # ─── 对外入口 ─────────────────────────────────────────

    async def capture(self, path: str) -> CaptureResult:
        """识别并入库单个文件，返回捕获结果。

        支持图片/文本后缀；不支持或超限 → ``ignored``（不入库）。
        """
        # Use the same absolute path for reading and provenance; do not resolve symlinks.
        path = str(Path(path).absolute())
        name = Path(path).name
        suffix = Path(path).suffix.lower()
        if suffix in IMAGE_SUFFIXES or suffix == ".pdf":
            return await self._capture_image(path, name)
        if suffix in TEXT_SUFFIXES:
            return await self._capture_text(path, name)
        log.info("directory capture ignored (unsupported suffix .%s): %s", suffix, path)
        return CaptureResult(
            status=STATUS_IGNORED,
            summary=f"忽略不支持的文件 {name}",
            ts=int(time.time()),
        )

    # ─── 内部：图片与 PDF 理解 ───────────────────────────────────

    async def _capture_image(self, path: str, name: str) -> CaptureResult:
        if self._media is None:
            return CaptureResult(status=STATUS_IGNORED, summary=f"当前图片与扫描 PDF 读取未启用：{name}", ts=int(time.time()))
        result = await self._media.understand(path)
        if not result or not str(result.get("text") or "").strip():
            return CaptureResult(status=STATUS_IGNORED, summary=f"资料未读取：{name}", ts=int(time.time()))
        source = FileCaptureSource(method="multimodal", path=path, captured_at=int(time.time()))
        raw = {"title": result.get("title") or name,
               "body": {"text": result["text"], "items": result.get("items", [])}}
        return await self._ingest(raw, name, source)

    # ─── 内部：文本直读 ───────────────────────────────────

    async def _capture_text(self, path: str, name: str) -> CaptureResult:
        size = _file_size(path)
        if size is None:
            return CaptureResult(
                status=STATUS_IGNORED,
                summary=f"忽略无法读取的文件 {name}",
                ts=int(time.time()),
            )
        if size > self._max_text_bytes:
            log.info("directory capture ignored (oversized text %d bytes): %s", size, path)
            return CaptureResult(
                status=STATUS_IGNORED,
                summary=f"忽略超大文件 {name}",
                ts=int(time.time()),
            )
        text = _read_text(path)
        if not text:
            # 空内容或读取失败（如目录被误当文本文件）：不入库，避免空证据
            log.info("directory capture ignored (unreadable or empty text): %s", path)
            return CaptureResult(
                status=STATUS_IGNORED,
                summary=f"忽略无法读取的文件 {name}",
                ts=int(time.time()),
            )
        source = FileCaptureSource(method="text", path=path, captured_at=int(time.time()))
        return await self._ingest({"title": name, "text": text}, name, source)

    # ─── 内部：共享入库管线 ───────────────────────────────

    async def _ingest(
        self, raw: dict[str, Any], name: str, source: FileCaptureSource
    ) -> CaptureResult:
        """raw → evidence → knowledge，返回 CaptureResult（敏感判定在先）。"""
        sensitivity = 0
        if self._security is not None:
            sensitivity = await self._security.detect_sensitivity(raw)

        evidence = await self._ingestion.ingest(
            self._source_type, raw, self._scope,
            sensitivity=sensitivity, capture_source=source,
        )
        item = await self._knowledge.structure(evidence)

        status = STATUS_SENSITIVE_QUARANTINED if sensitivity > 0 else STATUS_INGESTED
        summary = (
            f"隔离敏感文件 {name}" if sensitivity > 0 else f"记住文件 {name}"
        )
        return CaptureResult(
            status=status,
            summary=summary,
            evidence_id=evidence.id,
            knowledge_id=item.id,
            ts=int(time.time()),
        )


def _file_size(path: str) -> int | None:
    try:
        return Path(path).stat().st_size
    except OSError:
        log.warning("cannot stat %s", path, exc_info=True)
        return None


__all__ = [
    "CaptureResult",
    "IMAGE_SUFFIXES",
    "IngestBridge",
    "OcrAdapter",
    "STATUS_IGNORED",
    "STATUS_INGESTED",
    "STATUS_SENSITIVE_QUARANTINED",
    "TEXT_SUFFIXES",
]
