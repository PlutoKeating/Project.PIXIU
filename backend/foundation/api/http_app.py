"""PIXIU Foundation — API 网关 (FastAPI)

注册全部 11 个 REST 端点（按 docs/API.md 规格），
当前返回占位响应，后续各模块逐步实现业务逻辑。
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(
    title="PIXIU Memory API",
    description="面向银河麒麟 OS Agent 的去中心化分布式记忆系统 — API 网关",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─── 占位响应辅助 ────────────────────────────────────────

def _placeholder_response(**extra) -> dict:
    return {"status": "not_implemented", **extra}


# ─── 记忆写入 ────────────────────────────────────────────

@app.post("/memory/write", tags=["Memory"], summary="写入一条记忆")
async def memory_write():
    return _placeholder_response()


# ─── 混合检索 ────────────────────────────────────────────

@app.post("/memory/query", tags=["Memory"], summary="混合检索")
async def memory_query():
    return _placeholder_response()


# ─── 偏好提取 ────────────────────────────────────────────

@app.post("/preference/extract", tags=["Preference"], summary="触发偏好提取")
async def preference_extract():
    return _placeholder_response()


# ─── 偏好版本回溯 ────────────────────────────────────────

@app.get("/preference/{id}/history", tags=["Preference"], summary="偏好版本回溯")
async def preference_history(id: str):
    return _placeholder_response(id=id)


# ─── 自然语言遗忘 ────────────────────────────────────────

@app.post("/forget", tags=["Memory"], summary="自然语言遗忘")
async def forget():
    return _placeholder_response()


# ─── 冲突审计 ────────────────────────────────────────────

@app.get("/conflicts", tags=["Memory"], summary="冲突审计列表")
async def conflicts():
    return _placeholder_response()


# ─── 记忆流转 ────────────────────────────────────────────

@app.post("/memory/flow/promote", tags=["Flow"], summary="短/中期记忆沉淀到长期")
async def flow_promote():
    return _placeholder_response()


# ─── 设备配对 ────────────────────────────────────────────

@app.post("/sync/pair", tags=["Sync"], summary="设备配对")
async def sync_pair():
    return _placeholder_response()


# ─── 节点列表 ────────────────────────────────────────────

@app.get("/sync/peers", tags=["Sync"], summary="节点列表")
async def sync_peers():
    return _placeholder_response()


# ─── 同步状态 ────────────────────────────────────────────

@app.get("/sync/status", tags=["Sync"], summary="同步状态")
async def sync_status():
    return _placeholder_response()


# ─── 解绑设备 ────────────────────────────────────────────

@app.post("/sync/peers/{id}/revoke", tags=["Sync"], summary="解绑设备")
async def sync_revoke(id: str):
    return _placeholder_response(peer_id=id)
