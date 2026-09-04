#!/usr/bin/env python3
"""Render official D-02..D-04 documents and D-02 annexes A-01..A-05."""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Iterable


ROOT = Path(__file__).resolve().parents[1]
SUBMISSION_ROOT = ROOT / "submission"
FINAL_ROOT = SUBMISSION_ROOT / "final"
PLAN_PATH = SUBMISSION_ROOT / "submission-plan.json"
PENDING = re.compile(
    r"^(?:-\s*)?状态：.*(?:待补|未完成|工作稿|非最终候选)|\b(?:TBD|TODO)\b|【待(?:补|定)",
    re.IGNORECASE | re.MULTILINE,
)
SHA1 = re.compile(r"[0-9a-f]{40}")

DOCUMENTS = {
    "D-02": {
        "title": "PIXIU 技术方案及测试结果",
        "sources": [
            "docs/delivery/TECHNICAL_SOLUTION.md",
            "docs/delivery/TEST_REPORT.md",
        ],
        "outputs": [
            "02-技术方案及测试结果/PIXIU技术方案及测试结果.docx",
            "02-技术方案及测试结果/PIXIU技术方案及测试结果.pdf",
        ],
    },
    "D-03": {
        "title": "PIXIU 源码规范与许可证",
        "sources": ["docs/delivery/SOURCE_AND_LICENSES.md"],
        "outputs": ["03-源代码及规范/源码规范与许可证.pdf"],
    },
    "D-04": {
        "title": "PIXIU 部署指南",
        "sources": ["docs/delivery/DEPLOYMENT_GUIDE.md"],
        "outputs": ["04-部署文档/PIXIU部署指南.pdf"],
    },
    "A-01": {
        "title": "PIXIU 用户手册",
        "sources": ["docs/delivery/USER_MANUAL.md"],
        "outputs": ["02-技术方案及测试结果/01-用户手册/PIXIU用户手册.pdf"],
    },
    "A-02": {
        "title": "PIXIU 效果与测试报告",
        "sources": ["docs/delivery/TEST_REPORT.md"],
        "outputs": ["02-技术方案及测试结果/02-效果与测试证据/PIXIU效果与测试报告.pdf"],
    },
    "A-03": {
        "title": "PIXIU 记忆流转说明",
        "sources": ["docs/delivery/MEMORY_LIFECYCLE.md"],
        "outputs": ["02-技术方案及测试结果/03-记忆流转说明/PIXIU记忆流转说明.pdf"],
    },
    "A-04": {
        "title": "PIXIU 实际应用案例",
        "sources": ["docs/delivery/APPLICATION_CASES.md"],
        "outputs": ["02-技术方案及测试结果/04-实际应用案例/PIXIU实际应用案例.pdf"],
    },
    "A-05": {
        "title": "PIXIU 银河麒麟 V11 适配报告",
        "sources": ["docs/delivery/KYLIN_V11_ADAPTATION_REPORT.md"],
        "outputs": ["02-技术方案及测试结果/05-V11适配报告/PIXIU银河麒麟V11适配报告.pdf"],
    },
}


CSS = """
@page { size: A4; margin: 20mm 18mm 20mm 18mm; }
body { font-family: "Noto Sans CJK SC", "Microsoft YaHei", sans-serif;
       color: #172033; font-size: 10.5pt; line-height: 1.65; }
h1 { color: #143d59; font-size: 24pt; border-bottom: 2px solid #2a7f9e; padding-bottom: 8pt; }
h2 { color: #176b87; font-size: 17pt; margin-top: 20pt; }
h3 { color: #24566f; font-size: 13pt; }
p { margin: 5pt 0; } ul, ol { margin: 4pt 0 8pt 20pt; }
code { font-family: "LXGW WenKai Mono", monospace; background: #eef3f6; padding: 1pt 3pt; }
pre { font-family: "LXGW WenKai Mono", monospace; background: #eef3f6;
      border-left: 3px solid #2a7f9e; padding: 8pt; white-space: pre-wrap; }
blockquote { border-left: 4px solid #e8a838; margin: 8pt 0; padding: 6pt 10pt; background: #fff8e8; }
table { border-collapse: collapse; width: 100%; margin: 8pt 0 12pt 0; font-size: 9pt; }
th { background: #176b87; color: white; } th, td { border: 1px solid #aebbc5; padding: 5pt; vertical-align: top; }
.metadata { width: 100%; background: #edf6f8; border: 1px solid #9bc3d0; padding: 9pt; margin-bottom: 18pt; }
.draft { color: #a33; font-size: 14pt; font-weight: bold; }
.source-break { page-break-before: always; }
"""


def inline(value: str) -> str:
    escaped = html.escape(value, quote=True)
    escaped = re.sub(r"`([^`]+)`", r"<code>\1</code>", escaped)
    escaped = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", escaped)
    escaped = re.sub(r"\[([^]]+)]\(([^)]+)\)", r'<a href="\2">\1</a>', escaped)
    return escaped


def split_table(line: str) -> list[str]:
    return [cell.strip() for cell in line.strip().strip("|").split("|")]


def is_table_separator(line: str) -> bool:
    return all(re.fullmatch(r":?-{3,}:?", cell) for cell in split_table(line))


def markdown_body(markdown: str) -> str:
    lines = markdown.splitlines()
    output: list[str] = []
    paragraph: list[str] = []
    index = 0
    in_code = False
    code: list[str] = []
    list_kind: str | None = None

    def flush_paragraph() -> None:
        if paragraph:
            output.append("<p>" + inline(" ".join(paragraph)) + "</p>")
            paragraph.clear()

    def close_list() -> None:
        nonlocal list_kind
        if list_kind:
            output.append(f"</{list_kind}>")
            list_kind = None

    while index < len(lines):
        line = lines[index]
        if line.startswith("```"):
            flush_paragraph()
            close_list()
            if in_code:
                output.append("<pre>" + html.escape("\n".join(code)) + "</pre>")
                code.clear()
                in_code = False
            else:
                in_code = True
            index += 1
            continue
        if in_code:
            code.append(line)
            index += 1
            continue
        if line.startswith("|") and index + 1 < len(lines) and is_table_separator(lines[index + 1]):
            flush_paragraph()
            close_list()
            headers = split_table(line)
            index += 2
            rows: list[list[str]] = []
            while index < len(lines) and lines[index].startswith("|"):
                rows.append(split_table(lines[index]))
                index += 1
            output.append("<table><thead><tr>" + "".join(f"<th>{inline(cell)}</th>" for cell in headers) + "</tr></thead><tbody>")
            for row in rows:
                output.append("<tr>" + "".join(f"<td>{inline(cell)}</td>" for cell in row) + "</tr>")
            output.append("</tbody></table>")
            continue
        heading = re.match(r"^(#{1,6})\s+(.+)$", line)
        bullet = re.match(r"^\s*[-*]\s+(.+)$", line)
        numbered = re.match(r"^\s*\d+[.)]\s+(.+)$", line)
        if heading:
            flush_paragraph()
            close_list()
            level = min(len(heading.group(1)), 4)
            output.append(f"<h{level}>{inline(heading.group(2))}</h{level}>")
        elif bullet or numbered:
            flush_paragraph()
            kind = "ul" if bullet else "ol"
            if list_kind != kind:
                close_list()
                output.append(f"<{kind}>")
                list_kind = kind
            output.append(f"<li>{inline((bullet or numbered).group(1))}</li>")
        elif line.startswith(">"):
            flush_paragraph()
            close_list()
            output.append("<blockquote>" + inline(line.lstrip("> ")) + "</blockquote>")
        elif line.strip() in {"---", "***"}:
            flush_paragraph()
            close_list()
            output.append("<hr>")
        elif not line.strip():
            flush_paragraph()
            close_list()
        else:
            close_list()
            paragraph.append(line.strip())
        index += 1
    if in_code:
        raise ValueError("unclosed Markdown code fence")
    flush_paragraph()
    close_list()
    return "\n".join(output)


def render_html(title: str, sources: Iterable[tuple[str, str]], *, version: str, commit: str, draft: bool) -> str:
    sections: list[str] = []
    for index, (source_name, content) in enumerate(sources):
        css_class = ' class="source-break"' if index else ""
        sections.append(f"<p{css_class}><small>维护源：{html.escape(source_name)}</small></p>")
        sections.append(markdown_body(content))
    status = "草稿预览，不得提交" if draft else "最终候选生成稿，待人工审核"
    commit_display = "&#8203;".join(
        html.escape(commit[index : index + 8]) for index in range(0, len(commit), 8)
    )
    return (
        "<!doctype html><html><head><meta charset=\"utf-8\"><style>"
        + CSS
        + "</style></head><body>"
        + f"<h1>{html.escape(title)}</h1>"
        + f'<div class="metadata"><p class="{("draft" if draft else "final")}">{status}</p>'
        + f"<p>产品版本：{html.escape(version)}<br>Git commit：{commit_display}<br>生成方式：PIXIU 可复现交付文档流水线</p></div>"
        + "\n".join(sections)
        + "</body></html>"
    )


def load_plan() -> dict:
    value = json.loads(PLAN_PATH.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError("submission plan must be an object")
    return value


def validate_mapping() -> None:
    plan = load_plan()
    planned = {item["id"]: item for item in plan["deliverables"]}
    for identifier, document in DOCUMENTS.items():
        planned_documents = [
            path
            for path in planned[identifier]["paths"]
            if Path(path).suffix.lower() in {".docx", ".pdf"}
        ]
        if planned_documents != document["outputs"]:
            raise ValueError(f"{identifier} renderer outputs drift from submission plan")
        for source in document["sources"]:
            if not (ROOT / source).is_file():
                raise ValueError(f"missing document source: {source}")


def check_configuration() -> tuple[str, str]:
    validate_mapping()
    office = shutil.which("libreoffice") or shutil.which("soffice")
    pdfinfo = shutil.which("pdfinfo")
    if office is None or pdfinfo is None:
        raise ValueError("LibreOffice Writer and pdfinfo are required")
    return office, pdfinfo


def require_final_inputs(plan: dict) -> tuple[str, str]:
    commit = plan.get("release_commit")
    if not isinstance(commit, str) or not SHA1.fullmatch(commit):
        raise ValueError("release_commit must be fixed before final document rendering")
    head = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
    if head != commit or subprocess.check_output(["git", "-C", str(ROOT), "status", "--porcelain"], text=True):
        raise ValueError("final documents require a clean worktree at release_commit")
    pending = [
        name
        for name, state in plan.get("release_gates", {}).items()
        if name != "documents-reviewed" and state != "passed"
    ]
    if pending:
        raise ValueError("final document inputs are not ready: " + ", ".join(pending))
    for document in DOCUMENTS.values():
        for source in document["sources"]:
            content = (ROOT / source).read_text(encoding="utf-8")
            if PENDING.search(content):
                raise ValueError(f"final document source still contains pending markers: {source}")
    return (ROOT / "VERSION").read_text(encoding="utf-8").strip(), commit


def convert(office: str, pdfinfo: str, html_path: Path, stage: Path, profile: Path) -> tuple[Path, Path]:
    command = [office, "--headless", f"-env:UserInstallation={profile.as_uri()}"]
    subprocess.run(
        command + ["--convert-to", 'docx:Office Open XML Text', "--outdir", str(stage), str(html_path)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    docx = stage / (html_path.stem + ".docx")
    if not docx.is_file() or not zipfile_is_docx(docx):
        raise ValueError(f"LibreOffice did not create a valid DOCX for {html_path.stem}")
    subprocess.run(
        command + ["--convert-to", "pdf:writer_pdf_Export", "--outdir", str(stage), str(docx)],
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    pdf = stage / (html_path.stem + ".pdf")
    subprocess.run([pdfinfo, str(pdf)], check=True, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    return docx, pdf


def zipfile_is_docx(path: Path) -> bool:
    import zipfile

    try:
        with zipfile.ZipFile(path) as archive:
            names = set(archive.namelist())
            return "[Content_Types].xml" in names and "word/document.xml" in names
    except zipfile.BadZipFile:
        return False


def publish_file(source: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists():
        raise ValueError(f"refusing to overwrite existing document: {destination}")
    with source.open("rb") as input_stream, destination.open("xb") as output_stream:
        shutil.copyfileobj(input_stream, output_stream)


def render_all(output_root: Path, *, final: bool) -> None:
    office, pdfinfo = check_configuration()
    plan = load_plan()
    if final:
        version, commit = require_final_inputs(plan)
        package_root = output_root / plan["submission_name"]
    else:
        version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        commit = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
        package_root = output_root
    with tempfile.TemporaryDirectory() as temporary:
        stage = Path(temporary)
        profile = stage / "lo-profile"
        profile.mkdir()
        pending_outputs: list[tuple[Path, Path]] = []
        for identifier, document in DOCUMENTS.items():
            sources = [
                (source, (ROOT / source).read_text(encoding="utf-8"))
                for source in document["sources"]
            ]
            html_path = stage / f"pixiu-{identifier.lower()}.html"
            html_path.write_text(
                render_html(document["title"], sources, version=version, commit=commit, draft=not final),
                encoding="utf-8",
            )
            docx, pdf = convert(office, pdfinfo, html_path, stage, profile)
            for relative in document["outputs"]:
                source = docx if relative.endswith(".docx") else pdf
                # Drafts mirror the official five-category layout so review cannot
                # accidentally reintroduce flat or extra top-level deliverables.
                destination = package_root / relative
                pending_outputs.append((source, destination))
        existing = [str(destination) for _, destination in pending_outputs if destination.exists()]
        if existing:
            raise ValueError("refusing to overwrite existing documents: " + ", ".join(existing))
        created: list[Path] = []
        try:
            for source, destination in pending_outputs:
                publish_file(source, destination)
                created.append(destination)
        except BaseException:
            for destination in created:
                destination.unlink(missing_ok=True)
            raise


def main() -> int:
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--check", action="store_true")
    group.add_argument("--draft-output", type=Path)
    group.add_argument("--render-final", action="store_true")
    args = parser.parse_args()
    try:
        if args.check:
            check_configuration()
        elif args.draft_output:
            output = args.draft_output.resolve()
            if output == FINAL_ROOT.resolve() or FINAL_ROOT.resolve() in output.parents:
                raise ValueError("draft output must not be inside submission/final")
            render_all(output, final=False)
        else:
            render_all(FINAL_ROOT, final=True)
    except (KeyError, OSError, subprocess.CalledProcessError, ValueError, json.JSONDecodeError) as exc:
        print(f"document-render: {exc}", file=sys.stderr)
        return 1
    print("document-render: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
