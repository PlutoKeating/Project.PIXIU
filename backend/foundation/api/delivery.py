"""PIXIU Foundation — 递送层 API（批次④ B4-1：洞察流端点）。

端点注册模式与 ws.py 一致：本模块导入 http_app.app 并注册路由，
http_app.py 底部 ``from . import delivery`` 触发注册。
"""

from __future__ import annotations

from fastapi import Depends, Query

from .di import get_delivery_service
from .http_app import app

#: 洞察流面向本机用户域（聊天窗欢迎页建议）；与 monitor runtime 默认 scope 一致。
_INSIGHTS_SCOPE = "user:local"
_INSIGHTS_DEFAULT_LIMIT = 3
_INSIGHTS_MAX_LIMIT = 10


@app.get("/delivery/insights", tags=["Delivery"], summary="洞察流（最近高质量记忆）")
async def delivery_insights(
    limit: int = Query(_INSIGHTS_DEFAULT_LIMIT, ge=1, le=_INSIGHTS_MAX_LIMIT),
    delivery=Depends(get_delivery_service),
):
    """返回最近 24h 高质量记忆候选（quality 降序），供聊天窗欢迎页动态建议。

    limit 缺省 3、上限 10（>10 或 <1 → 400 INVALID_REQUEST，经 Query 校验 +
    统一 RequestValidationError handler，对齐 http_app.py monitor_log 先例）；
    MANUAL 冲突待处理时整体抑制返回空列表；空库/无候选 → {"insights": []}。
    """
    return {"insights": await delivery.insights(_INSIGHTS_SCOPE, limit=limit)}
