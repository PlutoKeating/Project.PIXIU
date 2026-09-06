# 问候语动态化 + 产品名统一 Design Spec

> 2026-09-06 代码复核：UserIdentity.cpp、ChatWindow 动态问候、t_user_identity.cpp 与翻译已实现；GECOS 首段 → USER → 用户回退。旧待规划/未勾选项不再代表代码缺口。
> 下文实施步骤、旧接口草图和测试数字保留作阶段历史，不作为当前操作手册；当前契约见 docs/API.md，发布见 docs/DELIVERY_PLAN.md。

> 日期：2026-09-01 · 状态：待规划
> 定位：①所有问候语从系统账户动态获取用户姓名（全名→login username 兜底）；②产品名统一为 PIXIU（貔貅只是其中文名/文化意象，不把用户称作貔貅）；③核对文档表述正确统一。

## [S1] 背景与目标

- 用户要求：**所有问候必须从系统获取用户名称**（账户设置的姓名全名；取不到全名用 login username 兜底）；**禁止把用户称作貔貅**；产品名统一为 **PIXIU**（貔貅与麒麟同为中国传统瑞兽，产品名 PIXIU=貔貅拼音，品牌意象成立）。
- 现状盘点：
  - 欢迎页问候 `ChatWindow.cpp:270` `tr("你好，我是 PIXIU")`——**产品自称**，未称呼用户，但问候不带用户姓名，不满足「问候要叫出用户名字」。
  - 全库「貔貅」出现均为**产品自称/品牌名**（`PIXIU 貔貅`顶栏、`PIXIU 貔貅 · 记忆管家`、About「PIXIU 貔貅是…」），**无任何「把用户称作貔貅」**——已合规。
  - 文档 `README.md:3`「PIXIU · 貔貅」、`DEVELOPMENT_PLAN.md:10`、`ARCHITECTURE.md:3`「项目代号：PIXIU（貔貅）」——产品名=PIXIU，貔貅为中文名/文化注解，表述一致正确。
  - 系统全名来源：`getent passwd $USER` 的 GECOS 字段（第 5 列）返回账户全名（本机实测 `PlutoKeating`）；`$USER`/`whoami` 是 login username（`pluto`）。Qt 侧可用 `QProcessEnvironment`/`qEnvironmentVariable("USER")` + 读 `/etc/passwd` 或 `getpwuid`。

## [S2] 问候语动态化（前端）

### [S2.1] 用户姓名获取
- 新增工具函数（如 `frontend/src/app/UserIdentity.cpp` 或加到既有 utils）：`QString displayUserName()`：
  1. 读 passwd getpwuid(getuid()) 的 GECOS 字段（第 5 列，逗号分隔首段为全名）；
  2. GECOS 空 → 回退 `qEnvironmentVariable("USER", "user")`（login username）；
  3. 再空 → "用户"（中英文安全兜底）。
- 依赖：标准库 + Qt（QString/QDir/获取 uid），无新第三方依赖。麒麟/UKUI 下 GECOS 通常由用户管理工具维护。

### [S2.2] 欢迎页问候改造
- `ChatWindow.cpp:270`：`tr("你好，我是 PIXIU")` → `tr("你好，%1。我是 PIXIU").arg(displayUserName())`（或 `tr("你好，%1")` + 副标题保留产品名信息——实现时选更自然的，说明理由；建议主标题带用户名「你好，X」，产品或助手身份放副标题/现有 subtitle 区，聚焦「叫出用户名字」）。
- **不把用户称貔貅**：问候文案中用户位置只放 `displayUserName()`，PIXIU 只出现在产品自称「我是 PIXIU」处。

## [S3] 产品名与文档统一

- 核对结果（S1 现状）：产品名 PIXIU、貔貅为中文名/文化意象，全库一致；**不把用户称貔貅**——已合规，无改动。
- 一处在 About 页文案（PixiuApp.cpp:1057）「PIXIU 貔貅是面向银河麒麟…」——产品自称，保留。
- 文档（README/DEVELOPMENT_PLAN/ARCHITECTURE）产品名表述正确统一，无需改。

## [S4] 测试策略
- 前端 ctest：
  - `displayUserName()` 单测：GECOS 全名 / GECOS 空回退 USER / 双空回退"用户"（可用注入 /etc/passwd 或 mock 读文件——实现时选最小 injectable 方案，说明）。**
  - ChatWindow 欢迎页：主标题含用户全名（或 mock displayUserName 后断言）；不称谓用户为貔貅（断言标题不含「貔貅」）。
  - 既有 welcome 标题断言（t_chat_window）同步更新。
- i18n：新模板文案 tr() 中文源文本（如 `tr("你好，%1")`），V-3 式 lupdate/lrelease 收编 0 unfinished。
- 回归：前端 OFF/ON ctest + regression.sh。

## [S5] 范围边界（不做）
- 不做用户头像/账户编辑 UI；不做多语言姓名本地化；不改系统账户；仅取姓名做问候。
- 不改产品名 PIXIU 的代码内标识（类名/PIXIU_VERSION 宏等）。

## [S6] 风险
- GECOS 字段可能含多个逗号分隔项（如办公室电话）——取首段为姓名；可能为空或非人名（如系统服务）——兜底 login username。
- 问候语含用户真实姓名——无隐私风险（本机显示，不上传；符合隐私政策「数据仅存本机」）。
