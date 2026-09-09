"""Run the real Qt editor against a disposable portable backend, never user data."""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from urllib.error import URLError
from urllib.request import Request, urlopen


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("qt_test", type=Path)
    args = parser.parse_args()
    binary = args.qt_test.resolve(strict=True)
    root = Path(__file__).resolve().parents[2]
    with tempfile.TemporaryDirectory(prefix="pixiu-edit-live-") as directory:
        task = Path(directory)
        env = {key: value for key, value in os.environ.items() if not key.startswith("PIXIU_")}
        env.update({
            "PIXIU_DB_PATH": str(task / "memory.db"), "PIXIU_DATA_DIR": str(task / "data"),
            "PIXIU_EMBEDDING": "portable", "PIXIU_VECTOR_STORE": "portable", "PIXIU_OCR": "portable",
            "PIXIU_SYNC_NETWORK_ENABLED": "false", "PIXIU_MONITOR_ENABLED": "false",
            "XDG_CONFIG_HOME": str(task / "config"), "XDG_DATA_HOME": str(task / "xdg-data"),
            "XDG_CACHE_HOME": str(task / "cache"), "XDG_STATE_HOME": str(task / "state"),
            "QT_QPA_PLATFORM": "offscreen",
        })
        with socket.socket() as listener, (task / "backend.log").open("w+") as log:
            listener.bind(("127.0.0.1", 0))
            listener.listen()
            url = f"http://127.0.0.1:{listener.getsockname()[1]}"
            process = subprocess.Popen(
                [sys.executable, "-m", "uvicorn", "backend.foundation.api:app", "--fd", str(listener.fileno())],
                pass_fds=(listener.fileno(),), cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT,
            )
            def request(path: str, payload: dict | None = None) -> dict:
                data = json.dumps(payload).encode() if payload is not None else None
                with urlopen(Request(url + path, data=data, headers={"Content-Type": "application/json"}), timeout=2) as response:
                    return json.load(response)
            try:
                deadline = time.monotonic() + 30
                while True:
                    if process.poll() is not None:
                        raise RuntimeError("isolated backend exited before readiness")
                    try:
                        if request("/health").get("status") == "ready":
                            break
                    except (URLError, TimeoutError):
                        pass
                    if time.monotonic() >= deadline:
                        raise RuntimeError("isolated backend readiness timeout")
                    time.sleep(0.1)
                capability = request("/capabilities")
                assert capability["embedding"]["runtime"] == "portable"
                assert capability["vector_store"]["runtime"] == "portable"
                request("/memory/write", {
                    "source_type": "MANUAL_CONFIG", "scope": "user:ui_test",
                    "raw": {"title": "isolated Qt editing fixture", "body": {
                        "text": "before live edit", "metadata": {"keep": True}}},
                    "idempotency_key": "live-editor-fixture",
                })
                record = request("/memory/query", {"text": "isolated Qt editing fixture",
                    "context_hint": {"scope": "user:ui_test", "top_k": 1}})
                assert record.get("source_knowledge")
                env.update({"PIXIU_BACKEND_URL": url, "PIXIU_MANAGEMENT_LIVE_TEST": "1",
                    "PIXIU_LIVE_KNOWLEDGE_ID": record["source_knowledge"]})
                subprocess.run([str(binary)], cwd=task, env=env, check=True, timeout=120)
                print("Real Qt editor + portable HTTP/SQLite integration: PASS (not native SDK evidence)")
            except BaseException:
                log.flush()
                log.seek(0)
                print(log.read(), file=sys.stderr)
                raise
            finally:
                process.terminate()
                try:
                    process.wait(timeout=10)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=10)


if __name__ == "__main__":
    main()
