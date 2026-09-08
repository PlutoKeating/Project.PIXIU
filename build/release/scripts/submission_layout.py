"""Paths and strict file checks for the frozen competition submission tree."""
from pathlib import Path
import re
import zipfile


def paths(root: Path) -> tuple[Path, Path, Path]:
    specification = (root / "docs/DELIVERY_PLAN.md").read_text()
    section = specification.split("### 0.4", 1)[1].split("### 0.5", 1)[0]
    name = re.findall(r"```text\n([^\n]+)\n```", section)[0]
    outer = root / "submission" / name
    return outer, outer / name, outer / "源代码"


def validate(root: Path, require_video: bool = False) -> list[str]:
    outer, materials, source = paths(root)
    expected = {
        materials / "项目报告.pptx", materials / "技术方案.doc",
        source / "PIXIU源代码.tar.gz",
    }
    video = materials / "演示视频.zip"
    if require_video or video.exists():
        expected.add(video)
    actual = {p for p in (root / "submission").rglob("*") if p.is_file()}
    if actual != expected:
        missing = sorted(str(p.relative_to(root)) for p in expected - actual)
        extra = sorted(str(p.relative_to(root)) for p in actual - expected)
        raise ValueError(f"提交文件集合错误：缺少 {len(missing)} 项 {missing[:5]}；多出 {len(extra)} 项 {extra[:5]}")
    directories = {p for p in (root / "submission").rglob("*") if p.is_dir()}
    if directories != {outer, materials, source}:
        raise ValueError("提交目录层级错误或包含多余目录")
    if any(p.is_symlink() for p in (root / "submission").rglob("*")):
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
