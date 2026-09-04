# openKylin Agent 宿主发行适配层

本目录只保存 PIXIU 对固定上游宿主的可审计构建适配，不修改
`third_party/kylin-agent`。上游固定 commit、许可证和证据要求以
`../agent-supply-chain-policy.json` 为准。

`patches/0001-build-coherent-offline-host.patch` 修正上游当前公开树中两类可复现的
构建断裂：入口仍引用已被 `GatewayService` 替代的旧类；CMake 同时编译一批不在当前
简化桌面流程中的半成品设置页，导致其未实现方法参与链接。补丁只保留当前主窗口、
会话、模型选择与 Runtime 聊天路径，并加入 `compat/pixiu_host_compat.cpp`，恢复真实
SSE 对话取消/完成语义以及窗口激活行为。它不是空桩，也不绕过 Runtime。

构建脚本必须在洁净的固定上游归档中应用补丁；任何 hunk 不匹配都立即失败。最终宿主
产物、完整已补丁源码、构建日志和摘要必须由供应链记录器生成，不能用本目录本身代替
目标 V11 构建证据。
