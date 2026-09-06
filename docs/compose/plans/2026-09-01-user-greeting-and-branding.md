# 问候语动态化 + 品牌一致性 Implementation Plan

> 2026-09-06 代码复核：UserIdentity.cpp、ChatWindow 动态问候、t_user_identity.cpp 与翻译已实现；GECOS 首段 → USER → 用户回退。旧待规划/未勾选项不再代表代码缺口。
> 下文实施步骤、旧接口草图和测试数字保留作阶段历史，不作为当前操作手册；当前契约见 docs/API.md，发布见 docs/DELIVERY_PLAN.md。

> **For agentic workers:** REQUIRED SUB-SKILL: Use compose:subagent (recommended) or compose:execute to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 所有问候语动态取系统用户姓名（全名→login username 兜底），产品名统一为 PIXIU（不把用户称貔貅），文档表述一致。

**Architecture:** 新增 `frontend/src/app/UserIdentity.cpp`（`displayUserName()` 从 passwd GECOS 取全名→`$USER` 兜底）；ChatWindow 欢迎页标题改 `tr("你好，%1").arg(displayUserName())`（产品身份 PIXIU 留副标题区）；i18n 收编。

**Tech Stack:** C++17 · Qt5 Widgets · QtTest(offscreen)

## Global Constraints

- **品牌**：产品名是 PIXIU；「貔貅」仅作中文名/文化意象，出现在「PIXIU 貔貅」产品自称处；**任何问候/文案不得把用户称作貔貅**。
- 用户姓名获取路径：passwd GECOS 全名 → `$USER`（login username）→ 空兜底。
- 无新第三方依赖（仅标准库 + Qt）。文案 tr() 中文源文本；offscreen 测试；禁止 push；单一逻辑一个提交。
- 本次改动并入当前发布（0.1.3 已构建；此改动后 bump 或 patch 由主代理定夺，本计划只实现+验证）。

---

## Task G-1: 用户姓名获取 + 欢迎页问候动态化

**Files:**
- Create: `frontend/src/app/UserIdentity.h/.cpp`（`displayUserName()`）
- Modify: `frontend/src/widgets/ChatWindow.cpp`（欢迎页标题问候带用户名）
- Modify: `frontend/CMakeLists.txt`（主目标 + t_chat_window/t_app_navigation/t_window_restore 源列表加 UserIdentity——编译 ChatWindow.cpp 的目标需同步，批次②教训）
- Test: `frontend/tests/t_chat_window.cpp`（或新建 t_user_identity.cpp）

**Interfaces:**
- Produces: `QString ui::displayUserName()`（或 `pixiu::displayUserName()`——命名空间按仓库惯例，读 UiTokens.h/既有 util 后用）；实现：`getpwuid(getuid())->pw_gecos` 取逗号分隔首段；空 → `qEnvironmentVariable("USER")`；再空 → `QStringLiteral("用户")`。
- ChatWindow 欢迎页：`title` 改 `tr("你好，%1").arg(displayUserName())`；subtitle 保留或加产品身份信息（如 `tr("我是 PIXIU — 问问你的记忆，或录入新的知识")`——实现时选更自然的，说明理由）。

- [ ] **Step 1: 写失败测试**（t_chat_window 断言欢迎页标题含动态用户名；新建 t_user_identity 断言 displayUserName 三路径——GECOS 全名/回退 USER/双空兜底用可注入的 uid/getpwuid——为可测，设计 `displayUserName(uid_t uid = getuid())` 参数或 mock passwd 读；以最小可注入方案为准说明）
- [ ] **Step 2: 运行验证失败**（displayUserName 未定义 / 标题未变）
- [ ] **Step 3: 实现**（UserIdentity.cpp + ChatWindow 欢迎页改造 + CMake 源列表）
- [ ] **Step 4: 运行验证通过**（`cmake -S frontend -B build/frontend -DPIXIU_HAVE_KYSDK=OFF -G Ninja && cmake --build build/frontend -j && QT_QPA_PLATFORM=offscreen ctest --test-dir build/frontend --output-on-failure` → 32+ 绿；断言标题含本机全名 PlutoKeating 且不含「貔貅」）
- [ ] **Step 5: i18n**（cd frontend/resources/i18n && lupdate … -ts pixiu_en_US.ts，补 `你好，%1` 译文，lrelease 0 unfinished）
- [ ] **Step 6: 提交** `git commit -m "feat(frontend): greet user by account name"`（含 i18n 或分开，说明）

**Covers:** [S2.1, S2.2, S4]

---

## 执行顺序
G-1 单任务。完成后主代理决定是否 bump 版本并发布（并入当前 0.1.3 或 patch）。
