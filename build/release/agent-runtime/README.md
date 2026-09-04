# Kylin Agent Runtime 离线 wheelhouse

`runtime-cp312.lock` 与 `build-tools-cp312.lock` 是经过目标环境验证并提交入库的
CPython 3.12/amd64 构建输入。`build-runtime-wheelhouse.sh prepare` 只按这两份锁及
固定 Runtime submodule 构建、下载；所有包必须匹配逐包 SHA-256，构建结果会从 wheel
的 METADATA 重新生成锁并逐字节比对，任何版本、哈希或闭包漂移都会失败。

随后应在目标 V11 的断网网络命名空间执行 `verify-offline`。验证使用全新 venv、
`--no-index --require-hashes` 安装全部 wheel，并导入 Runtime、aiohttp 与 Gateway
适配器，再核对 CLI 版本。构建下载与断网安装必须分成两个阶段，断网安装日志才可
交给 `record-agent-supply-chain.py runtime-wheelhouse`。

扫描不会因为第三方 wheel 而整体关闭。当前 `httpx==0.28.1`、
`pydantic==2.13.4` 与 `urllib3==2.7.0` 的 URL 解析/校验器各带一个 userinfo 文档
示例；策略仅按包版本、wheel 完整 SHA-256 和唯一成员路径放行这些静态示例。包内容
或命中位置发生任何变化都会重新失败，其他 wheel 仍不允许此类 URL。

Runtime 上游随 wheel 安装的若干可选 GitHub/Scrapling skill 会构造 userinfo URL，发行
构建在固定源码副本中删除这些与赛题无关的可选 skill；submodule 本身不改。唯一保留
命中是 `agent/redact.py` 的防泄漏正则表达式，记录器以成员路径和成员内容 SHA-256
精确放行。裁剪后出现任何额外命中都会在构建 wheel 前失败。

预构建扫描覆盖实际打包源码与数据；上游的 `tests/`、`website/`、`skills-old/` 不进入
wheel，作为只读参考事实保留但不混入发行输入。
