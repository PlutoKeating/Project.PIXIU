"""Capture event values shared by collectors and the delivery digest."""
from dataclasses import dataclass

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

