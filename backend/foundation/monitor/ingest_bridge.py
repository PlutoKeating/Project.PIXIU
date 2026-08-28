"""PIXIU Foundation — 目录捕获入库桥接（IngestBridge）

批次②「目录监视闭环」的核心入库端：把落盘文件经既有管线变为
evidence + knowledge（同进程直调，不经过 HTTP）：

- 图片（.png/.jpg/.jpeg/.bmp/.webp）→ 既有 OCR 适配器（get_ocr 返回的
  ``recognize(image_path) -> list[str]`` 接口）→ 组装 MANUAL 风格
  raw{title=文件名, text=识别文本}；
- 文本（.txt/.md/.csv，默认 ≤1MB）→ 直接读文本 → 同样 raw{title, text}；
- 其余后缀/超限文本 → ``ignored``，不入库。

两者共用 /memory/write 的既有同进程管线：
``ingestion.ingest(source_type, raw, scope, sensitivity=…)`` 产出 evidence，
``knowledge.structure(evidence)`` 产出 knowledge（对应的 HTTP handler 见
http_app.memory_write：ingest → structure → preference.extract → conflict.arbitrate；
本桥接只取 ingest + structure 两个必要环节，冲突仲裁/偏好提取属 BE-3 共享
流，不在监视桥接内重复）。

敏感处理（沿用既有 security.Detector 判定，不另起规则）：detector 命中
（sensitivity > 0）时仍入库但携带 sensitivity 标记、仅落本机 user:* scope，
事件状态记为 ``sensitive_quarantined`` —— 隔离语义 = 不出 shared:*/不参与
同步流转；sensitivity == 0 时状态为 ``ingested``。

异常不在此吞掉：由 DirectoryWatcher 统一 try/except 记录并继续监视。
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

from ..core.logger import get_logger

log = get_logger(__name__)

#: 文本直读后缀（≤ max_text_bytes）。
TEXT_SUFFIXES = frozenset({".txt", ".md", ".csv"})

#: 图片后缀（走 OCR）。
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
        scope: str = "user:local",
        max_text_bytes: int = 1024 * 1024,
        source_type: str = "MANUAL_CONFIG",
    ) -> None:
        #: 复用 api 层指定的同进程 pipeline 服务（ingest / knowledge / security）。
        self._ingestion = ingestion
        self._knowledge = knowledge
        #: security 可选：提供时按既有 detector 判定敏感度（sensitive_quarantined）。
        self._security = security
        self._ocr = ocr
        #: 捕获落库 scope —— 监视写入默认本机 user:*，敏感条目绝不入 shared:*。
        self._scope = scope
        self._max_text_bytes = max_text_bytes
        #: 入库 source_type（对齐计划：目录捕获组装 MANUAL 风格证据）。
        self._source_type = source_type

    # ─── 对外入口 ─────────────────────────────────────────

    async def capture(self, path: str) -> CaptureResult:
        """识别并入库单个文件，返回捕获结果。

        支持图片/文本后缀；不支持或超限 → ``ignored``（不入库）。
        """
        name = Path(path).name
        suffix = Path(path).suffix.lower()
        if suffix in IMAGE_SUFFIXES:
            return await self._capture_image(path, name)
        if suffix in TEXT_SUFFIXES:
            return await self._capture_text(path, name)
        log.info("directory capture ignored (unsupported suffix .%s): %s", suffix, path)
        return CaptureResult(
            status=STATUS_IGNORED,
            summary=f"忽略不支持的文件 {name}",
            ts=int(time.time()),
        )

    # ─── 内部：图片 OCR ───────────────────────────────────

    async def _capture_image(self, path: str, name: str) -> CaptureResult:
        if self._ocr is None:
            log.warning("image capture without OCR adapter: %s", path)
            return CaptureResult(
                status=STATUS_IGNORED,
                summary=f"忽略无法识别的图片 {name}",
                ts=int(time.time()),
            )
        # OCR 为同步 C 调用，放入线程池避免阻塞监视循环（对齐 http_app 的 to_thread）。
        lines = await asyncio.to_thread(self._ocr.recognize, path)
        text = "\n".join(lines)
        if not text.strip():
            # OCR 无有效文本：不入库（避免空证据），与 size 不可读→ignored 一致
            log.warning("image capture ignored (no OCR text): %s", path)
            return CaptureResult(
                status=STATUS_IGNORED,
                summary=f"忽略无法识别的图片 {name}",
                ts=int(time.time()),
            )
        return await self._ingest({"title": name, "text": text}, name)

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
        return await self._ingest({"title": name, "text": text}, name)

    # ─── 内部：共享入库管线 ───────────────────────────────

    async def _ingest(self, raw: dict[str, Any], name: str) -> CaptureResult:
        """raw → evidence → knowledge，返回 CaptureResult（敏感判定在先）。"""
        sensitivity = 0
        if self._security is not None:
            sensitivity = await self._security.detect_sensitivity(raw)

        evidence = await self._ingestion.ingest(
            self._source_type, raw, self._scope, sensitivity=sensitivity
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