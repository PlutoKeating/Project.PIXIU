"""确认式设备配对请求通道（GUI 主路径，QR/PIN 令牌为备选）。"""

from __future__ import annotations

import json
import secrets
import time

from .models import validate_id


class PairRequestError(ValueError):
    """配对请求参数非法（目标 ID 格式错误或自配对）。"""


_REQUEST_TTL_SECONDS = 60


class PairRequestManager:
    """创建/确认配对请求；accept 后由调用方（前端）走既有 /sync/pair 令牌入网。"""

    def __init__(self, store, identity) -> None:
        self._store = store
        self._identity = identity

    async def create(
        self,
        target_device_id: str,
        *,
        now: int | None = None,
        ttl_seconds: int = _REQUEST_TTL_SECONDS,
    ) -> dict:
        try:
            validate_id("device", target_device_id)
        except ValueError as exc:
            raise PairRequestError(str(exc)) from exc
        if target_device_id == self._identity.id:
            raise PairRequestError("cannot pair a device with itself")
        timestamp = int(time.time()) if now is None else now
        request_id = "req_" + secrets.token_hex(8)
        pin = f"{secrets.randbelow(1_000_000):06d}"
        payload = {
            "request_id": request_id,
            "from_device_id": self._identity.id,
            "target_device_id": target_device_id,
            "pin": pin,
            "expires_at": timestamp + ttl_seconds,
        }
        await self._store.set_meta(
            f"pair_request:{request_id}", json.dumps(payload)
        )
        return {
            "request_id": request_id,
            "pin": pin,
            "target_device_id": target_device_id,
            "expires_at": payload["expires_at"],
        }

    async def confirm(
        self,
        request_id: str,
        *,
        accept: bool,
        now: int | None = None,
    ) -> str:
        # 判定顺序：先查存在性 → 已记录 status 优先返回 → 再判 TTL。
        raw = await self._store.get_meta(f"pair_request:{request_id}")
        if raw is None:
            return "not_found"
        payload = json.loads(raw)
        if "status" in payload:
            return payload["status"]
        timestamp = int(time.time()) if now is None else now
        if payload["expires_at"] < timestamp:
            status = "expired"
        elif accept:
            # 由 SyncService 层完成令牌交换（见 Step 4）
            status = "accepted"
        else:
            status = "rejected"
        # 落 status 使 confirm 单次生效：后续 confirm 返回已记录状态，不再重新判定。
        payload["status"] = status
        await self._store.set_meta(
            f"pair_request:{request_id}", json.dumps(payload)
        )
        return status
