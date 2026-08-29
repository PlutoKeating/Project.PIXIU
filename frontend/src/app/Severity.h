#ifndef PIXIU_SEVERITY_H
#define PIXIU_SEVERITY_H

#include <QString>

// 冲突打扰级别归一化（F3-1 单一事实来源）。
//
// B3-3 起 conflict_detected 帧与 /conflicts 响应携带 severity
// （low / medium / high，按 resolution 派生）：
//   - MERGE    → low    ：自动合并，静默
//   - NEW_WINS → medium ：自动裁决，但用户应知晓
//   - MANUAL   → high   ：需人工确认
//
// 各消费方（PixiuApp 打扰分流 / MemoryPanel 条目着色）统一经 parseSeverity
// 归一化，避免同一映射散落多处后发散。约定：
//   - 比较前 toLower + trim：wire 值大小写不敏感；
//   - 未知 / 空值一律回落 High：宁可打扰不漏报（与后端
//     conflict_severity_for 的保守回落一致，见 backend/foundation/core/
//     models.py）。
//
// 本文件独立于 UiTokens.h 放置：severity 是领域语义（wire 契约值归一化），
// 不属于视觉设计令牌；且本头文件只依赖 QString，纯数据层（如 EventRouter）
// 也可安全消费，不会把 QApplication 拖进其依赖图，无 include 环。
namespace ui {

enum class Severity {
    Low,    // MERGE：自动合并，静默
    Medium, // NEW_WINS：自动裁决，用户应知晓
    High,   // MANUAL / 未知 / 空：需人工确认，保守回落
};

inline Severity parseSeverity(const QString &raw)
{
    const QString key = raw.trimmed().toLower();
    if (key == QStringLiteral("low")) {
        return Severity::Low;
    }
    if (key == QStringLiteral("medium")) {
        return Severity::Medium;
    }
    return Severity::High;
}

} // namespace ui

#endif // PIXIU_SEVERITY_H
