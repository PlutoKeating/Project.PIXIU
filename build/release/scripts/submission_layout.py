"""Paths and strict checks for the user-confirmed competition submission tree."""
from pathlib import Path
import json
import zipfile


def paths(root: Path) -> tuple[Path, Path, Path]:
    identity = json.loads((root / "docs/submission-identity.json").read_text())
    number, title = identity["work_number"], identity["work_title"]
    if not number.isdigit() or any(c in number + title for c in "/\\\n"):
        raise ValueError("作品编号或作品名称无效")
    name = number + "-" + title
    outer = root / "submission" / name
    return outer, outer / name, outer / "源代码"


def validate(root: Path, require_video: bool = False) -> list[str]:
    outer, materials, source = paths(root)
    # Human-authorized sibling workspaces are internal production evidence.
    # Neither workspace becomes part of the strict formal submission tree.
    production = {root / "submission" / name for name in
                  ("video-production", "presentation-production")}
    siblings = set((root / "submission").iterdir())
    if siblings - ({outer} | production):
        raise ValueError("提交根目录包含未授权的额外文件或目录")
    for workspace in production:
        if workspace.is_symlink() or (workspace.exists() and not workspace.is_dir()):
            raise ValueError("制作工作区必须是独立目录")
    expected = {
        materials / "项目报告.pptx", materials / "技术方案.doc",
        source / "PIXIU源代码.tar.gz",
    }
    video = materials / "演示视频.zip"
    if require_video or video.exists():
        expected.add(video)
    actual = {p for p in outer.rglob("*") if p.is_file()}
    if actual != expected:
        missing = sorted(str(p.relative_to(root)) for p in expected - actual)
        extra = sorted(str(p.relative_to(root)) for p in actual - expected)
        raise ValueError(f"提交文件集合错误：缺少 {len(missing)} 项 {missing[:5]}；多出 {len(extra)} 项 {extra[:5]}")
    directories = {outer} | {p for p in outer.rglob("*") if p.is_dir()}
    if directories != {outer, materials, source}:
        raise ValueError("提交目录层级错误或包含多余目录")
    if outer.is_symlink() or any(p.is_symlink() for p in outer.rglob("*")):
        raise ValueError("提交目录不允许符号链接")
    if (materials / "技术方案.doc").read_bytes()[:8] != bytes.fromhex("d0cf11e0a1b11ae1"):
        raise ValueError("技术方案.doc 必须是真正的 Word 二进制文档")
    with zipfile.ZipFile(materials / "项目报告.pptx") as archive:
        if archive.testzip() or "ppt/presentation.xml" not in archive.namelist():
            raise ValueError("项目报告.pptx 无法解析")
    if video.exists():
        # Use a conservative decimal interpretation for automated checking.
        if video.stat().st_size > 200_000_000:
            raise ValueError("视频压缩包超过 200M")
        with zipfile.ZipFile(video) as archive:
            if not archive.namelist() or archive.testzip():
                raise ValueError("视频压缩包为空或损坏")
    return [] if video.exists() else ["待放入演示视频.zip（5-10 分钟，大小不超过 200M）"]
