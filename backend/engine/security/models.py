"""引擎安全模块专用模型。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, model_validator

from backend.engine.security.detector import DetectionResult


class ForgetResult(BaseModel):
    """自然语言遗忘执行结果。

    status: pending（待确认）| forgotten（已执行）
    cascade_preview: 关联 evidence/关系的 **预估数量**，仅用于确认前预览；
        Engine 不会据此执行物理删除。
    """

    status: Literal["pending", "forgotten"]
    targets: list[dict[str, Any]] = Field(default_factory=list)
    forgotten_ids: list[str] = Field(default_factory=list)
    cascade_preview: dict[str, int] = Field(default_factory=dict)
    cascade: dict[str, int] = Field(default_factory=dict)
    irreversible: bool = True

    @model_validator(mode="after")
    def _sync_cascade_alias(self) -> "ForgetResult":
        if self.cascade_preview and not self.cascade:
            self.cascade = dict(self.cascade_preview)
        elif self.cascade and not self.cascade_preview:
            self.cascade_preview = dict(self.cascade)
        return self


__all__ = ["DetectionResult", "ForgetResult"]
