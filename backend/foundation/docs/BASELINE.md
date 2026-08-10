# Module C · Phase 0 基线报告

> 日期：2026-08-09
>
> 分支：`feat/foundation`
>
> 范围：只复核环境、代码现状与文档；未开始 Phase 1 加固代码。

## 1. 运行环境

- Conda 环境：`pixiu`
- Python：3.10.20
- 已验证可导入：`pytest`、`pytest_asyncio`、`pydantic`、`fastapi`、`aiosqlite`、`httpx`、`uvicorn`
- 两个官方麒麟 SDK submodule 均已初始化
- 生产配置仍只允许 `kylin` embedding；测试通过显式依赖注入使用 stub，不修改生产约束

## 2. 测试基线

以下命令均使用 `pixiu` 环境中的 Python 执行：

```bash
python -m pytest backend/foundation/tests -q --disable-warnings
# 222 passed, 1 warning

python -m pytest backend/engine/tests -q --disable-warnings
# 21 passed

python -m pytest backend/foundation/tests backend/engine/tests -q -ra
# 243 passed, 1 warning
```

唯一警告来自 Starlette `TestClient` 对当前 httpx 集成方式的弃用提示，不影响本阶段测试结果；
后续依赖升级时单独处理，避免在基线阶段扩大改动范围。

## 3. Git 基线

- 开始时无已跟踪文件改动；存在用户的未跟踪目录 `.mimocode/`，本阶段不触碰、不暂存
- 开始时当前分支相对 `origin/main` 领先 2 个本地提交
- 本阶段不执行 push、merge 或远程分支操作

## 4. 下一阶段入口条件

检索 MVP 已可调用，但 Phase 1 必须按以下顺序加固：

1. 持久化并恢复 knowledge↔entity 关联，保证数据库重启后图召回有效；
2. 使用 `asyncio.gather` 并行执行 BM25、ANN、Graph；
3. scope 实施硬过滤，禁止跨 scope 返回；
4. 实现 `time_range` 过滤；
5. 聚合仅计算查询匹配类别，并覆盖标准 434.50 金额场景；
6. 使用真实麒麟 embedding 与正式数据集复测召回率和 P95≤500ms。

## 5. 文档边界

本阶段只更新 `backend/foundation/docs/`。根目录文档仍含部分过时状态描述，超出 Module C
文件归属范围，应由 Human 或 Module D 在独立提交中统一修订。
