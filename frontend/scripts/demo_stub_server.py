#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PIXIU 前端视觉演示 stub（本地人工查看/截图专用）。

仅用于 Module A 在真实 UKUI 桌面会话中做视觉演示：在没有后端（或后端
对应端点尚未实现）时，按 docs/API.md 契约返回合理的演示数据，让
偏好/冲突/同步/证据卡/思考态/加载态/空态/失败重试等界面可被真实打开
查看。不修改 backend，不参与任何生产路径。

用法：
    python3 frontend/scripts/demo_stub_server.py [--port 8765]
        [--delay-query 2.5] [--delay-conflicts 1.5] [--delay-history 1.5]
        [--empty] [--badge 3] [--conflict-event]

选项：
    --delay-*     ：给查询/冲突/偏好历史接口增加人为延迟，便于截图加载态。
    --empty       ：冲突/同步/偏好历史返回空数据，便于截图空态。
    --badge N     ：WS 连接建立后发送 N 次 memory_ready，驱动悬浮球角标/通知。
    --conflict-event：WS 连接建立后发送一次 conflict_detected（角标 + 通知）。
"""

import argparse
import base64
import hashlib
import json
import re
import socket
import struct
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlparse

GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"
WS_CLIENTS = set()
WS_LOCK = threading.Lock()

DATA_PEERS = [
    {
        "id": "dev_abc",
        "name": "书房工作站",
        "is_self": True,
        "status": "ONLINE",
        "last_sync_ts": 1785052800,
        "pending_ops": 0,
    },
    {
        "id": "dev_def",
        "name": "客厅一体机",
        "is_self": False,
        "status": "ONLINE",
        "last_sync_ts": 1785052200,
        "pending_ops": 3,
    },
    {
        "id": "dev_ghi",
        "name": "麒麟笔记本",
        "is_self": False,
        "status": "OFFLINE",
        "last_sync_ts": 1785042000,
        "pending_ops": 1,
    },
]

DATA_SYNC_STATUS = {
    "domain": "shared:home",
    "peers_online": 2,
    "peers_total": 3,
    "pending_outgoing_ops": 0,
    "last_anti_entropy_ts": 1785052800,
    "total_ops_synced": 1285,
}

DATA_CONFLICTS = [
    {
        "id": "cfl_01H",
        "target_knowledge": "knw_02K",
        "field": "body.items[2].amount",
        "old_value": 156,
        "new_value": 186,
        "resolution": "NEW_WINS",
        "created_at": 1785052800,
        "knowledge_title": "2026年4月家庭支出清单",
    },
    {
        "id": "cfl_02H",
        "target_knowledge": "knw_03K",
        "field": "body.items[0].amount",
        "old_value": 328.5,
        "new_value": 368.5,
        "resolution": "MERGE",
        "created_at": 1785052200,
        "knowledge_title": "2026年4月家庭支出清单（修订）",
    },
]

DATA_PREFERENCE_HISTORY = {
    "id": "pref_output_style",
    "key": "output_style.compact",
    "current_version": 3,
    "history": [
        {
            "version": 1,
            "value": {"enabled": False},
            "updated_at": 1784978400,
        },
        {
            "version": 2,
            "value": {"enabled": True},
            "updated_at": 1784982000,
        },
        {
            "version": 3,
            "value": {"enabled": True, "detail_level": "high"},
            "updated_at": 1785052800,
        },
    ],
}

QUERY_ANSWER = {
    "answer": (
        "2026年4月，你们在水电燃气方面共支出 434.50 元，其中电费 210 元、"
        "水费 68.50 元、燃气费 156 元。"
    ),
    "source_evidence": ["evd_01H..."],
    "source_knowledge": "knw_02K...",
    "confidence": 0.93,
    "latency_ms": 210,
}


class _WsFrame:
    @staticmethod
    def encode_text(text):
        payload = text.encode("utf-8")
        header = b"\x81"
        size = len(payload)
        if size < 126:
            header += struct.pack("!B", size)
        elif size < 65536:
            header += struct.pack("!BH", 126, size)
        else:
            header += struct.pack("!BQ", 127, size)
        return header + payload


def ws_handshake(conn, headers):
    key = headers.get("Sec-WebSocket-Key", "")
    if not key:
        return False
    accept = base64.b64encode(
        hashlib.sha1((key + GUID).encode("ascii")).digest()
    ).decode("ascii")
    conn.sendall(
        (
            "HTTP/1.1 101 Switching Protocols\r\n"
            "Upgrade: websocket\r\n"
            "Connection: Upgrade\r\n"
            "Sec-WebSocket-Accept: {}\r\n\r\n"
        ).format(accept).encode("ascii")
    )
    return True


def serve_ws(conn, args):
    conn.settimeout(30)
    with WS_LOCK:
        WS_CLIENTS.add(conn)
    try:
        conn.sendall(_WsFrame.encode_text(json.dumps(
            {"event": "connected"}, ensure_ascii=False)))
        conn.sendall(_WsFrame.encode_text(json.dumps(
            {"event": "ping"}, ensure_ascii=False)))
        if args.conflict_event:
            time.sleep(2)
            conn.sendall(_WsFrame.encode_text(json.dumps(
                {
                    "event": "conflict_detected",
                    "data": {
                        "conflict_id": "cfl_demo_001",
                        "knowledge_title": "2026年4月家庭支出清单",
                        "field": "body.items[2].amount",
                        "old_value": 156,
                        "new_value": 186,
                    },
                },
                ensure_ascii=False,
            )))
        for i in range(max(0, args.badge)):
            time.sleep(1.5)
            conn.sendall(_WsFrame.encode_text(json.dumps(
                {
                    "event": "memory_ready",
                    "data": {
                        "evidence_id": "evd_demo_{:03d}".format(i),
                        "knowledge_id": "knw_demo_{:03d}".format(i),
                        "title": "演示记忆 #{}".format(i + 1),
                        "scope": "shared:home",
                    },
                },
                ensure_ascii=False,
            )))
        # 保持连接，周期心跳；直到客户端断开。
        while True:
            time.sleep(20)
            try:
                conn.sendall(_WsFrame.encode_text(json.dumps(
                    {"event": "ping"}, ensure_ascii=False)))
            except OSError:
                break
    except (OSError, socket.timeout):
        pass
    finally:
        with WS_LOCK:
            WS_CLIENTS.discard(conn)
        try:
            conn.close()
        except OSError:
            pass


def broadcast_event(name, data):
    frame = _WsFrame.encode_text(
        json.dumps({"event": name, "data": data}, ensure_ascii=False))
    with WS_LOCK:
        clients = list(WS_CLIENTS)
    for conn in clients:
        try:
            conn.sendall(frame)
        except OSError:
            pass


class DemoHandler(BaseHTTPRequestHandler):
    args = None

    def log_message(self, fmt, *args):
        sys.stdout.write("[demo-stub] " + (fmt % args) + "\n")
        sys.stdout.flush()

    def _json(self, payload, code=200):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _sleep(self, seconds):
        if seconds > 0:
            time.sleep(seconds)

    def _read_body(self):
        length = int(self.headers.get("Content-Length", 0))
        if length <= 0:
            return {}
        try:
            return json.loads(self.rfile.read(length).decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return {}

    def do_GET(self):
        path = urlparse(self.path).path
        if (path == "/events"
                and self.headers.get("Upgrade", "").lower() == "websocket"):
            self.close_connection = True
            if ws_handshake(self.connection, self.headers):
                serve_ws(self.connection, self.args)
            return
        if path == "/conflicts":
            self._sleep(self.args.delay_conflicts)
            self._json({"conflicts": [] if self.args.empty else DATA_CONFLICTS})
            return
        match = re.fullmatch(r"/preference/([^/]+)/history", path)
        if match:
            self._sleep(self.args.delay_history)
            pref_id = match.group(1)
            if self.args.empty:
                self._json(
                    {
                        "id": pref_id,
                        "key": "output_style.compact",
                        "current_version": 0,
                        "history": [],
                    }
                )
                return
            if pref_id not in ("pref_output_style", "pref_style"):
                self._json(
                    {
                        "error": "NOT_FOUND",
                        "message": "preference not found",
                        "request_id": "req_demo",
                    },
                    code=404,
                )
                return
            self._json(DATA_PREFERENCE_HISTORY)
            return
        if path == "/sync/peers":
            self._json(
                {"status": "ok", "peers": [] if self.args.empty else DATA_PEERS}
            )
            return
        if path == "/sync/status":
            self._json(DATA_SYNC_STATUS if not self.args.empty else {
                "domain": "shared:home",
                "peers_online": 0,
                "peers_total": 0,
                "pending_outgoing_ops": 0,
                "last_anti_entropy_ts": 0,
                "total_ops_synced": 0,
            })
            return
        self._json(
            {
                "error": "NOT_FOUND",
                "message": "unknown endpoint: {}".format(path),
                "request_id": "req_demo",
            },
            code=404,
        )

    def do_POST(self):
        path = urlparse(self.path).path
        body = self._read_body()
        if path == "/demo/conflict":
            broadcast_event("conflict_detected", {
                "conflict_id": "cfl_demo_001",
                "knowledge_title": "2026年4月家庭支出清单",
                "field": "body.items[2].amount",
                "old_value": 156,
                "new_value": 186,
            })
            self._json({"status": "ok"})
            return
        if path == "/demo/memory_ready":
            broadcast_event("memory_ready", {
                "evidence_id": "evd_demo_001",
                "knowledge_id": "knw_demo_001",
                "title": "演示记忆 #1",
                "scope": "shared:home",
            })
            self._json({"status": "ok"})
            return
        if path == "/memory/query":
            text = body.get("text", "")
            self._sleep(self.args.delay_query)
            if "失败" in text or "fail" in text:
                self._json(
                    {
                        "error": "INTERNAL_ERROR",
                        "message": "stub simulated query failure",
                        "request_id": "req_demo",
                    },
                    code=500,
                )
                return
            if "空" in text or "empty" in text:
                self._json(
                    {
                        "answer": "",
                        "source_evidence": [],
                        "source_knowledge": "",
                        "confidence": 0,
                        "latency_ms": 0,
                    }
                )
                return
            self._json(QUERY_ANSWER)
            return
        if path == "/memory/write":
            self._json(
                {
                    "evidence_id": "evd_01H...",
                    "status": "accepted",
                    "quality_score": 0.94,
                    "sensitivity": 0,
                    "latency_ms": 42,
                }
            )
            return
        if path == "/forget":
            if body.get("confirm"):
                self._json(
                    {
                        "status": "forgotten",
                        "forgotten_ids": ["knw_02K...", "evd_01H..."],
                        "latency_ms": 85,
                    }
                )
            else:
                self._json(
                    {
                        "targets": [
                            {
                                "type": "knowledge",
                                "id": "knw_02K...",
                                "title": "2026年4月家庭支出清单",
                            }
                        ],
                        "cascade": {
                            "evidence_count": 1,
                            "relation_count": 3,
                        },
                        "irreversible": True,
                    }
                )
            return
        if path == "/sync/pair":
            self._json(
                {
                    "peer_id": "dev_demo",
                    "device_name": "麒麟笔记本",
                    "domain": "shared:home",
                    "status": "paired",
                }
            )
            return
        match = re.fullmatch(r"/sync/peers/([^/]+)/revoke", path)
        if match:
            self._json(
                {
                    "status": "revoked",
                    "peer_id": match.group(1),
                    "domain": "shared:home",
                }
            )
            return
        if path == "/memory/flow/promote":
            self._json({"status": "not_implemented"})
            return
        self._json(
            {
                "error": "NOT_FOUND",
                "message": "unknown endpoint: {}".format(path),
                "request_id": "req_demo",
            },
            code=404,
        )


def main():
    parser = argparse.ArgumentParser(description="PIXIU 前端视觉演示 stub")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--delay-query", type=float, default=2.5)
    parser.add_argument("--delay-conflicts", type=float, default=1.5)
    parser.add_argument("--delay-history", type=float, default=1.5)
    parser.add_argument("--empty", action="store_true")
    parser.add_argument("--badge", type=int, default=3)
    parser.add_argument("--conflict-event", action="store_true")
    args = parser.parse_args()
    DemoHandler.args = args

    server = ThreadingHTTPServer(("127.0.0.1", args.port), DemoHandler)
    sys.stdout.write(
        "[demo-stub] listening on 127.0.0.1:{} (empty={}, badge={}, "
        "conflict_event={})\n".format(
            args.port, args.empty, args.badge, args.conflict_event))
    sys.stdout.flush()

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass


if __name__ == "__main__":
    main()
