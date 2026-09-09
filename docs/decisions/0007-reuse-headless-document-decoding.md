# 0007 — 复用固定版本的 headless 文档引擎

2026-09-10，按用户明确要求执行：复用开源工具，依赖随安装包携带，不保留已替换实现。

采用 Kreuzberg 4.10.3，源码 submodule `third_party/kreuzberg` 固定到
`0b3a73634ad29edbf6f9cdc850c630950ac8083d`（MIT）。上游保持只读。
其原生解码覆盖 Word/Excel/PowerPoint 新旧格式、ODF、RTF 和 PDF；PIXIU 在
`backend/foundation/documents` 提供统一内容块与私有文档登记，在
`backend/agent/mcp` / `dreaming` 提供受控工具与当前模型理解。

所有调用显式禁用 OCR、解析缓存及质量模型处理。图片意义由当前多模态模型读取，
不支持时提示该内容未读取。PDFium 页面渲染在进程内运行，不启动桌面程序。
不使用 LibreOffice、Poppler、独立图片模型选择或另一套 Office XML 解析器。
旧目录直接入库桥接已删除，目录统一经过 dreaming。

安装包携带固定 wheel 和其本地库；`runtime-cp312.lock` 记录实际 V11 wheelhouse
逐包 SHA-256。构建时联网下载，安装时 `--no-index --require-hashes`。
PDFium 7678 与 ONNX Runtime 1.24.2 版本来自固定上游发布工作流；许可证随包保留。
源码交付包含固定上游与对应许可证，源码归档不包含开发缓存或生成的 wheels。

已验证：通用环境真实 DOC/XLS/PPT、多工作表、嵌入图片及扫描 PDF；完整后端
934 项通过。V11 离线依赖安装和 headless 解码单独记录；该证据不代表真实多模态
模型理解、全部 Office 图形/公式覆盖或最终新装/升级验收。
