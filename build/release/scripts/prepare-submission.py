#!/usr/bin/env python3
"""Build the complete product source archive and validate the submission layout."""
from __future__ import annotations

import argparse
import gzip
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import subprocess
import sys
import tarfile

from submission_layout import paths, validate

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "build/release/agent-runtime"))
from source_scope import retained as runtime_retained

FRONTEND_INPUTS = {row["source"] for row in json.loads((ROOT / "build/release/agent-host/frontend-sources.json").read_text())}
SOURCE_DIRS = {"frontend", "backend", "build", "third_party"}
TECH_DOCS = {"docs/delivery/BUILD_AND_INSTALL.md"}
EXCLUDED_PARTS = {".git", ".github", ".gitlab", "website", "node_modules", "__pycache__", ".venv"}
RUNTIME_SOURCE_DIRS = {
    "agent", "tools", "kylin_agent_runtime_cli", "gateway", "tui_gateway", "cron",
    "acp_adapter", "plugins", "providers", "skills", "optional-skills",
}
BUILD_SCRIPTS = {
    "build-deb.sh", "functions.sh", "provision-target.sh", "prepare-agent-supply-chain.sh",
    "audit-agent-supply-chain.py", "record-agent-supply-chain.py", "source_checkout.py",
    "generate-release-manifest.py",
}


def upstream_selected(prefix: str, name: str) -> bool:
    parts = PurePosixPath(name).parts
    if EXCLUDED_PARTS.intersection(parts):
        return False
    if prefix in {"third_party/kylin-coreai-embedding/", "third_party/libkysdk-vector-engine-client/"}:
        return parts[0] == "include" or name in {"LICENSE", "COPYING", "NOTICE"}
    if prefix == "third_party/kylin-agent/":
        return parts[0] in {"include", "src", "res"} or name in {
            "CMakeLists.txt", "LICENSE", "README.md",
            "scripts/agent_runtime_install.sh", "scripts/agent_runtime_install_bak.sh",
        }
    if prefix == "third_party/kreuzberg/":
        # PIXIU consumes the hash-locked wheel, not the Rust/website monorepo.
        return name in {"LICENSE", "NOTICE"}
    if prefix == "third_party/kylin-agent-runtime/":
        if not runtime_retained(name):
            return False
        if len(parts) > 1:
            return parts[0] in RUNTIME_SOURCE_DIRS
        return name in {
            "run_agent.py", "model_tools.py", "toolsets.py", "batch_runner.py",
            "trajectory_compressor.py", "toolset_distributions.py", "cli.py",
            "kylin_agent_runtime_bootstrap.py", "kylin_agent_runtime_constants.py",
            "kylin_agent_runtime_state.py", "kylin_agent_runtime_time.py",
            "kylin_agent_runtime_logging.py", "utils.py", "setup.py",
            "pyproject.toml", "LICENSE", "README.md", "version",
        }
    if any(p in {"test", "tests", "docs", "doc", "demo", "examples", ".vscode", ".idea"} for p in parts):
        return False
    return not parts[0].startswith(".")

VERIFY = '''#!/usr/bin/env python3
"""Verify every delivered source file against SOURCE-MANIFEST.json."""
import hashlib, json
from pathlib import Path
root = Path(__file__).resolve().parent
manifest = json.loads((root / "SOURCE-MANIFEST.json").read_text())
for entry in manifest["files"]:
    path = root / entry["path"]
    data = path.read_bytes() if not path.is_symlink() else path.readlink().as_posix().encode()
    assert hashlib.sha256(data).hexdigest() == entry["sha256"], entry["path"]
print("源码文件摘要全部通过：", len(manifest["files"]))
'''


def git(root: Path, *args: str) -> bytes:
    return subprocess.check_output(["git", "-C", str(root), *args])


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def selected(name: str) -> bool:
    path = PurePosixPath(name)
    if EXCLUDED_PARTS.intersection(path.parts) or path.name in {".gitkeep", ".gitignore"}:
        return False
    if path.suffix == ".md" and name != "backend/agent/SOUL.md":
        return False
    if name in {"VERSION", "LICENSE", "NOTICE"}:
        return True
    if path.parts[0] == "third_party":
        return len(path.parts) == 2  # pinned submodule traversal only
    if path.parts[0] == "frontend":
        return name in FRONTEND_INPUTS or name == "frontend/CMakeLists.txt" or name.startswith(("frontend/host/", "frontend/resources/"))
    if path.parts[0] == "backend":
        if any(p in {"tests", "test", "docs", "scripts", "evidence"} for p in path.parts[2:]):
            return False
        # foundation/eval is imported by the application and is product code.
        if "eval" in path.parts[2:] and not name.startswith("backend/foundation/eval/"):
            return False
        return len(path.parts)>1 and path.parts[1] in {"engine", "foundation", "agent", "platform", "requirements.txt"}
    if name.startswith("build/release/"):
        rel=path.parts[2:]
        if len(rel)==1:
            return rel[0] in {"Makefile", "agent-supply-chain-policy.json", "README.md"}
        if rel[0]=="scripts":
            return len(rel)==2 and rel[1] in BUILD_SCRIPTS
        return rel[0] in {"agent-host", "agent-runtime", "debian", "profiles", "keys"}
    return False


def collect(root: Path) -> tuple[dict, dict]:
    entries = {}
    modules = {}

    def walk(repo: Path, prefix: str = "") -> None:
        for record in git(repo, "ls-files", "--stage", "-z").split(b"\0"):
            if not record:
                continue
            header, raw = record.split(b"\t", 1)
            mode, oid, stage = header.decode().split()
            name = raw.decode()
            target = prefix + name
            parts = PurePosixPath(name).parts
            if prefix and not upstream_selected(prefix, name):
                continue
            if not prefix and not selected(target):
                continue
            if mode == "160000":
                child = repo / name
                actual = git(child, "rev-parse", "HEAD").decode().strip()
                if actual != oid or git(child, "status", "--porcelain"):
                    raise ValueError("子模块必须与固定提交一致且清洁：" + target)
                modules[target] = actual
                walk(child, target + "/")
                continue
            path = repo / name
            if not path.exists() and not path.is_symlink():
                raise ValueError("受跟踪源码缺失：" + target)
            data = path.readlink().as_posix().encode() if path.is_symlink() else path.read_bytes()
            if data.startswith(b"version https://git-lfs.github.com/spec/v1\n"):
                raise ValueError("源码中存在未下载的 LFS 指针：" + target)
            original = sha(data)
            # Corresponding source must not redistribute credentials from upstream examples.
            if target in {
                "third_party/kylin-agent/scripts/agent_runtime_install.sh",
                "third_party/kylin-agent/scripts/agent_runtime_install_bak.sh",
                "third_party/kylin-agent/src/services/gatewayservice.cpp",
            }:
                data = re.sub(rb"((?:https?|git)://)[^/\s:@]+:[^/\s@]+@", rb"\1", data)
            entries[target] = {"mode": mode, "data": data, "repositorySha256": original}

    walk(root)
    for name, data in {
        "README.md": (root / "docs/delivery/BUILD_AND_INSTALL.md").read_bytes(),
        "verify-source.py": VERIFY.encode(),
    }.items():
        entries[name] = {"mode": "100755" if name.endswith(".py") else "100644", "data": data}
    return entries, modules


def build_source(root: Path, output: Path | None = None) -> None:
    entries, modules = collect(root)
    required = {"third_party/kylin-agent", "third_party/kylin-agent-runtime",
                "third_party/kreuzberg", "third_party/kylin-coreai-embedding",
                "third_party/libkysdk-vector-engine-client"}
    if not required.issubset(modules):
        raise ValueError("缺少正式产品依赖的固定上游源码")
    manifest = {
        "source_scope": "minimal-build", "schema": 1, "version": (root / "VERSION").read_text().strip(),
        "sourceCommit": git(root, "rev-parse", "HEAD").decode().strip(),
        "sourceTreeClean": not bool(git(root, "status", "--porcelain", "--", *sorted(SOURCE_DIRS), *sorted(TECH_DOCS))),
        "submodules": modules,
        "submoduleEpochs": {name: int(git(root / name, "show", "-s", "--format=%ct", "HEAD")) for name in modules},
        "files": [{"path": name, "mode": entry["mode"], "sha256": sha(entry["data"]),
                   **({"repositorySha256": entry["repositorySha256"]} if "repositorySha256" in entry else {})}
                  for name, entry in sorted(entries.items())],
    }
    entries["SOURCE-MANIFEST.json"] = {"mode": "100644", "data": (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode()}
    _, _, source = paths(root)
    output = output or source / "PIXIU源代码.tar.gz"
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(".tmp")
    with temporary.open("wb") as raw, gzip.GzipFile(filename="", mode="wb", fileobj=raw, mtime=0) as compressed, tarfile.open(fileobj=compressed, mode="w") as archive:
        for name, entry in sorted(entries.items()):
            info = tarfile.TarInfo("PIXIU/" + name)
            info.mode = 0o755 if entry["mode"] == "100755" else 0o644
            data = entry["data"]
            if entry["mode"] == "120000":
                info.type = tarfile.SYMTYPE
                info.linkname = data.decode()
                archive.addfile(info)
            else:
                info.size = len(data)
                archive.addfile(info, io.BytesIO(data))
    temporary.replace(output)
    print(f"源码包已生成：{len(manifest['files'])} 个文件，{len(modules)} 个固定上游")


def check_source(root: Path) -> dict:
    _, _, source = paths(root)
    expected, modules = collect(root)
    with tarfile.open(source / "PIXIU源代码.tar.gz") as archive:
        names = archive.getnames()
        if len(names) != len(set(names)) or set(names) != {"PIXIU/" + p for p in expected} | {"PIXIU/SOURCE-MANIFEST.json"}:
            raise ValueError("源码文件集合与当前产品源码不一致")
        manifest = json.load(archive.extractfile("PIXIU/SOURCE-MANIFEST.json"))
        if manifest["version"] != (root / "VERSION").read_text().strip() or manifest["submodules"] != modules:
            raise ValueError("源码版本或固定上游不一致")
        records = {record["path"]: record for record in manifest["files"]}
        if len(records) != len(manifest["files"]) or set(records) != set(expected):
            raise ValueError("源码清单不完整")
        for name, entry in expected.items():
            member = archive.getmember("PIXIU/" + name)
            if member.issym() != (entry["mode"] == "120000") or records[name]["mode"] != entry["mode"]:
                raise ValueError("源码类型不一致：" + name)
            expected_mode = 0o755 if entry["mode"] == "100755" else 0o644
            if member.mode != expected_mode:
                raise ValueError("源码权限不一致：" + name)
            data = member.linkname.encode() if member.issym() else archive.extractfile(member).read()
            if data != entry["data"] or sha(data) != records[name]["sha256"]:
                raise ValueError("源码摘要不一致：" + name)
    return {"sourceFiles": len(expected), "version": manifest["version"]}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["build-source", "check"])
    parser.add_argument("--require-video", action="store_true")
    parser.add_argument("--output", type=Path, help="Optional source archive destination")
    args = parser.parse_args()
    if args.command == "build-source":
        build_source(ROOT, args.output)
    else:
        missing = validate(ROOT, args.require_video)
        print(json.dumps({"layout": "pass", **check_source(ROOT), "pending": missing}, ensure_ascii=False))


if __name__ == "__main__":
    main()
