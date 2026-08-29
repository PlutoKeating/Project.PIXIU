"""PIXIU Foundation — 递送层 API（批次④：B4-1 洞察流、B4-2 定时简报）。

端点注册模式与 ws.py 一致：本模块导入 http_app.app 并注册路由，
http_app.py 底部 ``from . import delivery`` 触发注册。
"""

from __future__ import annotations

from datetime import datetime

from fastapi import Depends, HTTPException, Query

from .di import get_delivery_digest_service, get_delivery_service
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


@app.get("/delivery/digest", tags=["Delivery"], summary="定时简报（当日记忆沉淀）")
async def delivery_digest(
    date: str | None = Query(None, description="YYYY-MM-DD；缺省今天"),
    digest_service=Depends(get_delivery_digest_service),
):
    """按日聚合当日 monitor_log 事件生成中文简报，供前端「今日简报」入口消费。

    date 缺省今天（本地时区）；非法日期（非严格 YYYY-MM-DD / 无效日历日如
    2026-02-30，含空串）→ 400 INVALID_REQUEST（错误体 {error, message, request_id}）；
    空日 → summary 为「当日无新记忆」。简报为规则化模板，不含敏感原文。
    """
    # 仅缺省（参数未传）回退今天；显式空串 "" 属非法日期，走 400 而非静默回退。
    day = date if date is not None else datetime.now().strftime("%Y-%m-%d")
    try:
        return await digest_service.digest(day)
    except ValueError:
        # 非法日期：服务/存储层以 ValueError 表达（MonitorLogStore 直连防御），
        # API 层映射为契约错误码 400 INVALID_REQUEST。
        raise HTTPException(status_code=400, detail="INVALID_REQUEST") from None
