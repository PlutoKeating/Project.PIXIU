"""引擎安全模块专用模型。"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field


class ForgetResult(BaseModel):
    """自然语言遗忘执行结果。

    status: pending（待确认）| forgotten（已执行）
    """

    status: Literal["pending", "forgotten"]
    targets: list[dict[str, Any]] = Field(default_factory=list)
    forgotten_ids: list[str] = Field(default_factory=list)
    cascade: dict[str, int] = Field(default_factory=dict)
    irreversible: bool = True
