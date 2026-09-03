from __future__ import annotations

import importlib.util
import unittest
from pathlib import Path


SCRIPT = Path(__file__).resolve().parents[1] / "render_documents.py"
SPEC = importlib.util.spec_from_file_location("render_documents", SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(MODULE)


class RenderDocumentsTest(unittest.TestCase):
    def test_markdown_renderer_preserves_document_structures(self) -> None:
        rendered = MODULE.markdown_body(
            """# 标题

- 条目

| 名称 | 状态 |
|---|---|
| Agent | **通过** |

```text
pixiu --version
```

> 注意事项
"""
        )
        self.assertIn("<h1>标题</h1>", rendered)
        self.assertIn("<ul>", rendered)
        self.assertIn("<table>", rendered)
        self.assertIn("<strong>通过</strong>", rendered)
        self.assertIn("<pre>pixiu --version</pre>", rendered)
        self.assertIn("<blockquote>注意事项</blockquote>", rendered)

    def test_draft_has_watermark_and_traceability(self) -> None:
        rendered = MODULE.render_html(
            "PIXIU 文档",
            [("docs/source.md", "# 内容")],
            version="1.2.3",
            commit="a" * 40,
            draft=True,
        )
        self.assertIn("草稿预览，不得提交", rendered)
        self.assertIn("docs/source.md", rendered)
        self.assertIn("1.2.3", rendered)
        self.assertEqual(rendered.count("aaaaaaaa"), 5)

    def test_repository_plan_and_renderer_outputs_match(self) -> None:
        MODULE.validate_mapping()


if __name__ == "__main__":
    unittest.main()
