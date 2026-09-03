#!/usr/bin/env python3
"""Capture the final acceptance report through strict installed KylinSDK components."""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Awaitable, Callable

COMPONENT_ROOT = Path(__file__).resolve().parents[2]
if str(COMPONENT_ROOT) not in sys.path:
    sys.path.insert(0, str(COMPONENT_ROOT))

from backend.foundation.eval.eval import EvalService
from backend.foundation.eval.models import PredictionRecord
from backend.foundation.eval.reference import build_reference_dataset
from backend.scripts.capture_eval_predictions import _capture


EVIDENCE_CLASS = "kylin-v11-final-eval-capture"
SHA256 = re.compile(r"[0-9a-f]{64}")
COMMIT = re.compile(r"[0-9a-f]{40}")


class CaptureError(RuntimeError):
    pass


def read_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CaptureError("native evidence is not readable JSON") from exc
    if not isinstance(value, dict):
        raise CaptureError("native evidence must be a JSON object")
    return value


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
    except OSError as exc:
        raise CaptureError("input file is not readable") from exc
    return digest.hexdigest()


def validate_native(value: dict[str, Any]) -> dict[str, str]:
    release = value.get("release")
    candidate = value.get("candidate_package")
    capabilities = value.get("capabilities")
    checks = value.get("checks")
    if not all(isinstance(item, dict) for item in (release, candidate, capabilities, checks)):
        raise CaptureError("native evidence is incomplete")
    platform = capabilities.get("platform")
    runtimes = (capabilities.get("embedding"), capabilities.get("vector_store"))
    if not (
        value.get("evidence_class") == "kylin-v11-native-sdk-product-lifecycle"
        and value.get("real_device_evidence") is True
        and value.get("status") == "pass"
        and release.get("profile") == "kylin-v11-native-x86_64"
        and release.get("architecture") == "amd64"
        and release.get("kysdk") == "ON"
        and release.get("install_strict") is True
        and COMMIT.fullmatch(str(release.get("git_commit", "")))
        and SHA256.fullmatch(str(candidate.get("sha256", "")))
        and isinstance(platform, dict)
        and platform.get("family") == "kylin"
        and platform.get("version_major") == "11"
        and capabilities.get("contest_ready") is True
        and all(
            isinstance(runtime, dict)
            and runtime.get("configured") == "kylin"
            and runtime.get("runtime") == "kylin"
            and runtime.get("compliant") is True
            for runtime in runtimes
        )
        and all(
            checks.get(name) == "passed"
            for name in ("contest_ready", "memory_write", "vector_search", "vector_delete")
        )
    ):
        raise CaptureError("native evidence is not a strict passing V11 lifecycle")
    return {
        "git_commit": value["release"]["git_commit"],
        "candidate_package_sha256": value["candidate_package"]["sha256"],
        "product_version": value["release"]["product_version"],
        "debian_version": value["release"]["debian_version"],
    }


def validate_execution(value: dict[str, Any], identity: dict[str, str] | None = None) -> None:
    if not (
        value.get("evidence_class") == EVIDENCE_CLASS
        and value.get("real_device_evidence") is True
        and value.get("platform") == "kylin-v11-amd64"
        and value.get("execution_mode") == "installed-components-isolated-evaluation-state"
        and value.get("python_origin") == "/usr/lib/pixiu/venv/bin/python"
        and value.get("component_origin") == "/usr/lib/pixiu"
        and value.get("embedding_runtime") == "kylin"
        and value.get("vector_store_runtime") == "kylin"
        and value.get("isolated_sqlite") is True
        and value.get("isolated_vector_database") is True
        and COMMIT.fullmatch(str(value.get("git_commit", "")))
        and SHA256.fullmatch(str(value.get("candidate_package_sha256", "")))
        and SHA256.fullmatch(str(value.get("native_evidence_sha256", "")))
    ):
        raise CaptureError("evaluation execution provenance is not strict Kylin V11")
    if identity is not None and any(
        value.get(name) != identity[name]
        for name in ("git_commit", "candidate_package_sha256")
    ):
        raise CaptureError("evaluation execution provenance identifies another release")


async def capture_report(
    native_path: Path,
    *,
    runner: Callable[..., Awaitable[list[dict[str, Any]]]] = _capture,
    installed_python: str = "/usr/lib/pixiu/venv/bin/python",
    component_origin: str = "/usr/lib/pixiu",
) -> dict[str, Any]:
    native = read_json(native_path)
    identity = validate_native(native)
    with tempfile.TemporaryDirectory(prefix="pixiu-final-eval-") as directory:
        root = Path(directory)
        predictions = await runner(
            str(root / "pixiu.db"),
            runtime="kylin",
            vector_db_path=str(root / "vector-engine.db"),
            vector_app_id="pixiu-final-eval",
            vector_collection=f"pixiu_final_eval_{os.getpid()}_{time.time_ns()}",
        )
    dataset = build_reference_dataset()
    records = [PredictionRecord.model_validate(item) for item in predictions]
    report = EvalService().evaluate_predictions(dataset, records).model_dump(mode="json")
    execution = {
        "evidence_class": EVIDENCE_CLASS,
        "real_device_evidence": True,
        "platform": "kylin-v11-amd64",
        "execution_mode": "installed-components-isolated-evaluation-state",
        "python_origin": installed_python,
        "component_origin": component_origin,
        "embedding_runtime": "kylin",
        "vector_store_runtime": "kylin",
        "isolated_sqlite": True,
        "isolated_vector_database": True,
        "git_commit": identity["git_commit"],
        "candidate_package_sha256": identity["candidate_package_sha256"],
        "native_evidence_sha256": file_sha256(native_path),
    }
    validate_execution(execution, identity)
    report["execution"] = execution
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--native-evidence", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    output = args.output.resolve()
    try:
        if output.exists():
            raise CaptureError("refusing to overwrite final evaluation report")
        executable = Path(sys.executable).absolute().as_posix()
        source = Path(__file__).absolute().as_posix()
        if executable != "/usr/lib/pixiu/venv/bin/python":
            raise CaptureError("final evaluation must use the installed PIXIU interpreter")
        if not source.startswith("/usr/lib/pixiu/backend/scripts/"):
            raise CaptureError("final evaluation must use the installed PIXIU components")
        report = asyncio.run(capture_report(args.native_evidence.resolve()))
        output.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=output.parent, delete=False
        ) as stream:
            json.dump(report, stream, ensure_ascii=False, indent=2, sort_keys=True)
            stream.write("\n")
            temporary = Path(stream.name)
        temporary.replace(output)
    except (CaptureError, OSError, ValueError) as exc:
        print(f"final-eval-capture: {exc}", file=sys.stderr)
        return 1
    print("final-eval-capture: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
