"""delivery/ —— 递送层（批次④ B4）。

洞察流（insights）与后续定时简报（digest，B4-2）等主动递送服务；
规则化生成、无 LLM 依赖、离线可运行。
"""

from backend.engine.delivery.insights import DeliveryInsightsService

__all__ = ["DeliveryInsightsService"]
