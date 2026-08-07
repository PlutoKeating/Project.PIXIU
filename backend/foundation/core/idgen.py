"""PIXIU Foundation — ULID 前缀 ID 生成器

为每种实体类型生成可读、可排序、全局唯一的标识符。
格式：<prefix>_<26-char ULID>
"""

from __future__ import annotations

import time
import os

# ULID 字符集 (Crockford Base32)
_ENCODING = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"

_LAST_TS = 0
_LAST_RAND = 0


def _ulid() -> str:
    """生成 26 字符 ULID（时间戳 10 位 + 随机 16 位）。"""
    global _LAST_TS, _LAST_RAND

    ts = int(time.time() * 1000)
    rand = int.from_bytes(os.urandom(10), "big")

    if ts == _LAST_TS:
        rand = max(rand, _LAST_RAND + 1)
    _LAST_TS = ts
    _LAST_RAND = rand

    chars = []
    for i in range(9, -1, -1):
        chars.append(_ENCODING[(ts >> (5 * i)) & 0x1F])
    for i in range(15, -1, -1):
        chars.append(_ENCODING[(rand >> (5 * i)) & 0x1F])

    return "".join(chars)


def gen_evidence_id() -> str:
    return f"evd_{_ulid()}"


def gen_knowledge_id() -> str:
    return f"knw_{_ulid()}"


def gen_pref_id() -> str:
    return f"pref_{_ulid()}"


def gen_conflict_id() -> str:
    return f"cfl_{_ulid()}"


def gen_device_id() -> str:
    return f"dev_{_ulid()}"


def gen_sync_op_id() -> str:
    return f"sync_{_ulid()}"


def gen_entity_id() -> str:
    return f"ent_{_ulid()}"


def gen_request_id() -> str:
    return f"req_{_ulid()}"
