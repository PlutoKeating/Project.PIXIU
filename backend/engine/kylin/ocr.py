"""OCR 适配：麒麟 kysdk-ocr 优先，结构化文本降级。

底层为 C++ 接口 SDK（libkyocr），经 pybind11 模块
``backend.engine.kylin._kylin_ocr`` 暴露给 Python。
构建方式见 ``backend/engine/kylin/cpp/README.md``。
"""

from __future__ import annotations

import logging
from pathlib import Path

from backend.engine.kylin.errors import KylinSDKUnavailableError

logger = logging.getLogger(__name__)

# 无麒麟 SDK 时：仅接受已带识别文本的结构化输入（与既有 OcrConnector 对齐），
# 不做真实图像识别——诚实降级，不伪造结果。


def _load_native():
    try:
        from backend.engine.kylin import _kylin_ocr as native
    except ImportError as exc:
        raise KylinSDKUnavailableError(
            "麒麟 kysdk-ocr 原生扩展未加载：请安装 libkysdk-ocr 并按 "
            "backend/engine/kylin/cpp/README.md 构建 _kylin_ocr。"
        ) from exc
    return native


class KylinOcr:
    """麒麟 OCR 客户端（同步接口）：图片路径 -> 文字行列表。"""

    def __init__(self) -> None:
        native = _load_native()
        self._impl = native.KylinOcr()

    def recognize(self, image_path: str | Path, nums: int = 4) -> list[str]:
        lines: list[str] = self._impl.recognize(str(image_path), int(nums))
        return [line for line in (str(item) for item in lines) if line.strip()]


class StructuredTextOcr:
    """无 SDK 时的降级实现：透传输入中已存在的文本字段。

    仅支持 raw 中已含 text/ocr_text 的结构化输入；对图像路径直接抛错，
    保证调用方不会把“未识别”误当成“识别为空”。
    """

    def recognize(self, image_path: str | Path, nums: int = 4) -> list[str]:
        raise KylinSDKUnavailableError(
            "当前环境无麒麟 kysdk-ocr：图像识别不可用（仅支持已含文本的"
            "结构化输入）。"
        )


def get_ocr(backend: str = "auto"):
    """按能力选择 OCR 后端。

    ``auto`` 优先麒麟 SDK，缺失时降级为结构化文本透传并告警；
    ``kylin`` 用于验收并保持严格失败；``portable`` 强制结构化透传。
    """
    if backend == "portable":
        return StructuredTextOcr()
    if backend == "kylin":
        return KylinOcr()
    if backend != "auto":
        raise ValueError("ocr backend must be auto, kylin, or portable")
    try:
        return KylinOcr()
    except KylinSDKUnavailableError:
        logger.warning("Kylin OCR unavailable; using structured-text fallback")
        return StructuredTextOcr()


__all__ = [
    "KylinOcr",
    "KylinSDKUnavailableError",
    "StructuredTextOcr",
    "get_ocr",
]
