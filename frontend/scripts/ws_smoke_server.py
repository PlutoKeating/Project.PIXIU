#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""PIXIU 前端 WS 事件冒烟桩（测试专用）。

仅用于 Module A 的 UI 事件冒烟：在没有后端（或后端 /events 未修复）时，
模拟 `/events` 端点的 WebSocket 握手与业务事件帧，驱动前端验证
memory_ready 通知 / 角标等 UI 行为。不参与任何生产路径。

用法：
    python3 frontend/scripts/ws_smoke_server.py --port 8765 \
        --event memory_ready --title "Phase 8 冒烟记忆" \
        --knowledge-id knw_smoke_001 --hold 10

连接建立后依次发送 connected / ping 控制帧与一个业务事件帧，保持连接
--hold 秒后断开，并继续接受下一次连接（覆盖前端退避重连路径）。
"""

import argparse
import base64
import hashlib
import json
import socket
import struct
import sys
import time

GUID = "258EAFA5-E914-47DA-95CA-C5AB0DC85B11"


def recv_exact(conn, size):
    data = b""
    while len(data) < size:
        chunk = conn.recv(size - len(data))
        if not chunk:
            raise ConnectionError("peer closed during handshake")
        data += chunk
    return data


def read_http_headers(conn):
    data = b""
    while b"\r\n\r\n" not in data:
        chunk = conn.recv(4096)
        if not chunk:
            raise ConnectionError("peer closed before request headers")
        data += chunk
    head, _ = data.split(b"\r\n\r\n", 1)
    lines = head.decode("latin-1").split("\r\n")
    headers = {}
    for line in lines[1:]:
        if ":" in line:
            key, value = line.split(":", 1)
            headers[key.strip().lower()] = value.strip()
    return headers


def send_text_frame(conn, text):
    payload = text.encode("utf-8")
    header = b"\x81"
    size = len(payload)
    if size < 126:
        header += struct.pack("!B", size)
    elif size < 65536:
        header += struct.pack("!BH", 126, size)
    else:
        header += struct.pack("!BQ", 127, size)
    conn.sendall(header + payload)


def handle_client(conn, args):
    headers = read_http_headers(conn)
    key = headers.get("sec-websocket-key", "")
    if not key:
        return
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

    send_text_frame(conn, json.dumps({"event": "connected"}, ensure_ascii=False))
    send_text_frame(conn, json.dumps({"event": "ping"}, ensure_ascii=False))

    payload = {"event": args.event, "data": {}}
    if args.event == "memory_ready":
        payload["data"] = {
            "evidence_id": args.evidence_id,
            "knowledge_id": args.knowledge_id,
            "title": args.title,
            "scope": "shared:home",
        }
    elif args.event == "conflict_detected":
        payload["data"] = {
            "conflict_id": "cfl_smoke_001",
            "knowledge_title": args.title,
            "field": "body.items[2].amount",
            "old_value": 156,
            "new_value": 186,
        }
    if args.delay > 0:
        time.sleep(args.delay)
    send_text_frame(conn, json.dumps(payload, ensure_ascii=False))
    sys.stdout.write(
        "[ws-smoke] sent {} with title={!r}, holding {}s (delay {}s)\n".format(
            args.event, args.title, args.hold, args.delay
        )
    )
    sys.stdout.flush()
    time.sleep(args.hold)
    conn.close()


def main():
    parser = argparse.ArgumentParser(description="PIXIU 前端 WS 事件冒烟桩（测试专用）")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--event", default="memory_ready",
                        choices=["memory_ready", "conflict_detected"])
    parser.add_argument("--title", default="Phase 8 冒烟记忆")
    parser.add_argument("--knowledge-id", default="knw_smoke_001")
    parser.add_argument("--evidence-id", default="evd_smoke_001")
    parser.add_argument("--delay", type=float, default=0.5,
                        help="发送业务事件前等待秒数（便于先完成其他验证）")
    parser.add_argument("--hold", type=float, default=10.0)
    args = parser.parse_args()

    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((args.host, args.port))
    server.listen(5)
    sys.stdout.write(
        "[ws-smoke] listening on ws://{}:{}/events\n".format(args.host, args.port)
    )
    sys.stdout.flush()
    try:
        while True:
            conn, _ = server.accept()
            try:
                handle_client(conn, args)
            except (ConnectionError, OSError) as exc:
                sys.stdout.write("[ws-smoke] client session ended: {}\n".format(exc))
                sys.stdout.flush()
                try:
                    conn.close()
                except OSError:
                    pass
    except KeyboardInterrupt:
        pass
    finally:
        server.close()


if __name__ == "__main__":
    main()
