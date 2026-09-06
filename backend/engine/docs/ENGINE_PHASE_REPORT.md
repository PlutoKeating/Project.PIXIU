# ENGINE_PHASE_REPORT

## Engine 阶段开发总结

## 1. 阶段目标

本阶段基于 `ENGINE_AUDIT_REPORT` 对 backend/engine 进行优化。

目标：

-   优先解决 Engine 自身逻辑问题
-   保持 Foundation 接口边界
-   不通过修改底层 schema 绕过问题
-   为后续模块联调提供稳定基础

重点覆盖：

-   Kylin适配
-   Ingest
-   Preference
-   Knowledge
-   Security

------------------------------------------------------------------------

# 2. 已完成工作

## 2.1 Kylin SDK适配

完成：

-   Python 与麒麟 C SDK 调用链路整理
-   pybind11 binding 接入
-   Embedding接口验证

当前状态：

-   Engine侧 embedding 调用链已打通
-   生产路径使用真实 SDK，不使用 mock 降级

待后续：

-   双 SDK 已完成 V11 构建和阶段性产品链验证；最终版本需重跑自动原生取证。
-   OCR 适配源码已接入，但单包未构建 `_kylin_ocr`。
-   VectorStore 已注入写入、检索和遗忘；不再是待接线状态。

------------------------------------------------------------------------

## 2.2 Ingest模块优化

目标：

提升外部数据进入系统后的规范化能力。

完成：

-   Connector数据流梳理
-   alias规则优化
-   实体名称规范化
-   测试补充

效果：

-   不同来源数据可以进入统一 Evidence 流程
-   为后续 Knowledge结构化提供稳定输入

说明：

当前同时提供 OCR 结构化结果处理和 `engine/kylin/ocr.py` 原生适配；
图片识别依赖可用的 `_kylin_ocr` 扩展。现有整包构建只强制构建 Embedding/Vector，
不能将原生 OCR 源码存在或结构化文本通过写成整包图片识别已验收。

------------------------------------------------------------------------

## 2.3 Preference模块优化

原问题：

-   Adapter 已存在，但没有真正接入 Service
-   Extractor规则较为分散，不易扩展

完成：

-   Adapter 接入 PreferenceService
-   Extractor 改为规则驱动结构
-   偏好数据格式统一
-   增加单元测试

效果：

-   新增偏好类型时无需大幅修改核心逻辑
-   偏好解析结构更加清晰

------------------------------------------------------------------------

## 2.4 Knowledge模块优化

目标：

增强 Evidence 到 Knowledge 的结构化能力。

完成：

-   四类 Knowledge 类型识别优化
    -   FACT
    -   WORKFLOW
    -   CASE
    -   TEMPLATE
-   Graph相关逻辑完善
-   实体一致性处理
-   补充测试覆盖

当前限制：

-   FTS索引问题属于 Foundation 环境问题
-   未通过修改 Foundation 绕过

------------------------------------------------------------------------

## 2.5 Security模块优化

目标：

提高敏感信息检测和遗忘功能可靠性。

完成：

Detector：

-   增强敏感信息识别边界
-   补充测试覆盖

Forget：

-   优化匹配逻辑
-   增强scope隔离
-   提高目标定位准确性

当前状态：

-   Engine侧能力完善
-   真正级联删除和tombstone需要模块协作

------------------------------------------------------------------------

# 3. 当前测试状态

当前：

-   新增 Engine 单元测试通过
-   部分全链路测试受到外部环境影响

主要阻塞：

SQLite FTS5 trigram 环境问题。

现象：

-   Knowledge写入阶段依赖 FTS索引
-   当前Python环境SQLite版本不支持 trigram tokenizer

判断：

该问题属于 Foundation/运行环境问题，不属于 Engine业务逻辑错误。

------------------------------------------------------------------------

# 4. 当前未解决问题

## Foundation相关

需要后续协作：

-   SQLite FTS环境统一
-   Repository事务边界
-   跨模块级联删除

## Kylin相关

需要后续验证：

-   OCR SDK接入
-   Vector检索链路

## Engine后续优化

可以继续：

-   Conflict语义升级
-   更完善的知识检索策略

------------------------------------------------------------------------

# 5. 当前阶段总结

本阶段完成：

-   Kylin Embedding适配
-   Ingest优化
-   Preference优化
-   Knowledge优化
-   Security优化

目前 Engine 主要业务模块已经完成一轮整理。
