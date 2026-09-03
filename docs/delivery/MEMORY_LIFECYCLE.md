# D-08 Agent 记忆流转说明

- 更新日期：2026-09-03
- 状态：架构基线；Module E 生命周期实证待补

## 三层边界

- 短期：当前 run/turn 的原始消息、计划和工具上下文，随上下文窗口受控清理。
- 中期：会话/项目摘要、未完成事项和中间结果，可跨若干小时或天更新与归档。
- 长期：版本化偏好、事实、工作流、案例和模板，跨会话检索并受 scope/遗忘约束。

## 生命周期映射

`prefetch` 在每轮前按 query/session/scope 召回长期记忆；`sync_turn` 把完整用户与
助手轮次作为 `CONVERSATION` evidence；工具结果以 `TOOL_RESULT` 保存 run/turn/
tool-call/审批来源；`on_pre_compress` 生成中期摘要；session 切换/结束触发
promote、demote、TTL 与清理；显式记忆工具支持查询、记住、遗忘和同步状态。

## 分布式与安全

只有允许共享的 scope 进入 CRDT/Gossip/反熵；私人记忆留在本机。晋升不删除来源，
冲突保留并发证据，遗忘产生可传播墓碑。召回前应用敏感过滤和 scope 隔离，委派给
子 Agent 时只传最小必要上下文。

当前后端 flow 已有基础结构，`CONVERSATION`、Agent 关联 ID 与完成态持久化幂等已
实现；失败恢复、context 公共写入与真实生命周期触发尚未实现。完成前不得把本说明
当成完整运行证据。
