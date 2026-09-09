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
import tarfile

from submission_layout import paths, validate

ROOT = Path(__file__).resolve().parents[3]
SOURCE_DIRS = {"frontend", "backend", "build", "third_party", ".github"}
RUNTIME_SOURCE_DIRS = {
    ".github", ".plans", "acp_adapter", "acp_registry", "agent", "assets", "cron",
    "datagen-config-examples", "docker", "docs", "draw", "embeddings", "evals",
    "gateway", "kylin_agent_runtime_cli", "locales", "models", "nix", "optional-skills",
    "packaging", "plans", "plugins", "pre-llm", "providers", "quick-test", "scripts",
    "skills-old", "skills", "tests", "tools", "tui_gateway", "ui-tui", "web",
}
TECH_DOCS = {"docs/ARCHITECTURE.md", "docs/API.md", "docs/QUICK_START.md",
             "docs/acceptance/acceptance-baseline-2026-08-24.md",
             "docs/acceptance/acceptance-baseline-2026-08-24.json"}
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
    if name == "build/release/document-export-manifest.json":
        return False
    if path.parts[0] in SOURCE_DIRS:
        return not name.startswith(("build/release/out/", "build/release/evidence/", "build/release/dist/"))
    return name in TECH_DOCS or (len(path.parts) == 1 and name in {
        "VERSION", "LICENSE", "NOTICE", ".gitmodules", ".gitignore", "pyproject.toml",
        "requirements.txt", "CMakeLists.txt", "Makefile", "uv.lock",
    })


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
            if prefix == "third_party/kylin-agent-runtime/" and len(parts) > 1 and parts[0] not in RUNTIME_SOURCE_DIRS:
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
        "README.md": (root / "docs/delivery/SOURCE_AND_LICENSES.md").read_bytes(),
        "verify-source.py": VERIFY.encode(),
    }.items():
        entries[name] = {"mode": "100755" if name.endswith(".py") else "100644", "data": data}
    return entries, modules


def build_source(root: Path) -> None:
    entries, modules = collect(root)
    if len(modules) != 4:
        raise ValueError("必须包含四个固定上游源码")
    manifest = {
        "schema": 1, "version": (root / "VERSION").read_text().strip(),
        "sourceCommit": git(root, "rev-parse", "HEAD").decode().strip(),
        "sourceTreeClean": not bool(git(root, "status", "--porcelain", "--", *sorted(SOURCE_DIRS), *sorted(TECH_DOCS))),
        "submodules": modules,
        "files": [{"path": name, "mode": entry["mode"], "sha256": sha(entry["data"]),
                   **({"repositorySha256": entry["repositorySha256"]} if "repositorySha256" in entry else {})}
                  for name, entry in sorted(entries.items())],
    }
    entries["SOURCE-MANIFEST.json"] = {"mode": "100644", "data": (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode()}
    _, _, source = paths(root)
    source.mkdir(parents=True, exist_ok=True)
    output = source / "PIXIU源代码.tar.gz"
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
    print(f"源码包已生成：{len(manifest['files'])} 个文件，四个固定上游")


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
    args = parser.parse_args()
    if args.command == "build-source":
        build_source(ROOT)
    else:
        missing = validate(ROOT, args.require_video)
        print(json.dumps({"layout": "pass", **check_source(ROOT), "pending": missing}, ensure_ascii=False))


if __name__ == "__main__":
    main()
