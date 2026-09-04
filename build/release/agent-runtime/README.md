# Kylin Agent Runtime 离线 wheelhouse

`build-runtime-wheelhouse.sh prepare` 从固定 Runtime submodule 构建项目 wheel，并解析
基础依赖及 Gateway 明确需要的 `aiohttp==3.13.3` 全闭包。`make-wheel-lock.py` 从每个
wheel 的 METADATA 读取名称/版本并写入逐包 SHA-256 锁文件。

随后应在目标 V11 的断网网络命名空间执行 `verify-offline`。验证使用全新 venv、
`--no-index --require-hashes` 安装全部 wheel，并导入 Runtime、aiohttp 与 Gateway
适配器，再核对 CLI 版本。构建下载与断网安装必须分成两个阶段，断网安装日志才可
交给 `record-agent-supply-chain.py runtime-wheelhouse`。
