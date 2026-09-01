#ifndef PIXIU_USER_IDENTITY_H
#define PIXIU_USER_IDENTITY_H

#include <QString>

#include <pwd.h>
#include <unistd.h>

// 用户身份工具：从系统账户信息解析可展示的用户姓名（问候语动态化）。
//
// 命名空间选择：与 UiTokens.h 同用 `ui`，保持 UI 侧工具一致；独立成一对
// UserIdentity.h/.cpp 而非并入 UiTokens.h——UiTokens.h 有意做成 header-only
// （注释明示“token 实现只依赖 Qt 基础类型，各控件与测试可直接包含，无需为
// 每个测试目标重复编译源文件”），而 UserIdentity 需要 .cpp（getpwuid /
// qEnvironmentVariable 等），若合入 UiTokens.h 会迫使每个包含它的测试目标
// 都链接 UserIdentity.cpp，违反该文件的 header-only 契约。
namespace ui {

// 可注入的 passwd 读取器（与 getpwuid 同签名）。
// 单测通过它构造假条目 / 空条目 / 缺条目，确定性验证三路径，不依赖
// 机器 GECOS 状态；这是比“仅传假 uid”更小的可注入方案——假 uid 在系统
// 中通常查不到条目（getpwuid 返回 NULL），无法构造“有全名”的路径，
// 因此必须注入读取器才能覆盖全部三态。
using PasswdReader = struct passwd *(*)(uid_t);

// 从系统账户信息解析可展示的用户姓名：
//   1. passwd GECOS 字段逗号分隔首段（账户全名）；
//   2. GECOS 为空（或条目缺失）→ 回退 $USER（login username）；
//   3. 再空 → QStringLiteral("用户")。
// `uid` 默认取当前进程真实用户；`reader` 默认 getpwuid，可注入以便单测。
QString displayUserName(uid_t uid = getuid(), PasswdReader reader = getpwuid);

} // namespace ui

#endif // PIXIU_USER_IDENTITY_H
