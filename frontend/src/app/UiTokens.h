#ifndef PIXIU_UI_TOKENS_H
#define PIXIU_UI_TOKENS_H

#include <QApplication>
#include <QColor>
#include <QFont>
#include <QPalette>
#include <QString>

// 统一 UI 设计令牌（Module A Design System 单一来源）。
//
// 对应 frontend/docs/ARCHITECTURE.md §7：
//   - 配色：语义色从 QPalette / 明暗主题派生，控件中禁止再出现内联色值；
//   - 字号分级：标题 14pt / 正文 11pt / 辅助 9pt（§7.2）；
//   - 间距栅格：4 / 8 / 12 / 16（§7.3）；
//   - 圆角：窗口 12 / 卡片 8 / 按钮 8 / 气泡 10（§7.3）；
//   - 危险按钮：统一由 dangerButtonStyle() 生成，明暗主题自适应。
//
// 本文件为 header-only：token 实现只依赖 Qt 基础类型，各控件与测试可直接
// 包含，无需为每个测试目标重复编译源文件。
namespace ui {

// 语义色角色：明暗主题下分别取值，避免控件自行写死颜色。
enum class Role {
    Success,   // 在线 / 成功 / 本机
    Warning,   // 连接中 / 待处理
    Error,     // 异常 / 失败 / 危险
    Muted,     // 次要文本 / 占位 / 离线
    Accent,    // 强调 / 链接（跟随 palette Highlight）
    Badge,     // 未读角标
    DangerBackground,
    DangerText,
};

// 当前应用 Palette 是否处于深色主题。
inline bool isDarkPalette()
{
    const QColor window = QApplication::palette().color(QPalette::Window);
    return window.lightness() < 128;
}

// 语义色：浅色主题使用既有验收色值，深色主题使用提亮后的可读变体。
inline QColor semanticColor(Role role)
{
    const QPalette palette = QApplication::palette();
    const bool dark = isDarkPalette();
    switch (role) {
    case Role::Success:
        return dark ? QColor(0x7e, 0xe2, 0xa8) : QColor(0x18, 0x80, 0x38);
    case Role::Warning:
        return dark ? QColor(0xf0, 0xa6, 0x4a) : QColor(0xb0, 0x60, 0x00);
    case Role::Error:
        return dark ? QColor(0xf2, 0x8b, 0x82) : QColor(0xd9, 0x30, 0x25);
    case Role::Muted:
        return palette.color(QPalette::Mid);
    case Role::Accent:
        return palette.color(QPalette::Highlight);
    case Role::Badge:
        return dark ? QColor(0xef, 0x53, 0x50) : QColor(0xd9, 0x30, 0x25);
    case Role::DangerBackground:
        return dark ? QColor(0xef, 0x53, 0x50) : QColor(0xd9, 0x30, 0x25);
    case Role::DangerText:
        return QColor(0xff, 0xff, 0xff);
    }
    return palette.color(QPalette::Text);
}

// 语义色文本样式（仅颜色；字号由 styles.qss 按 objectName 统一控制）。
inline QString textStyle(Role role)
{
    return QStringLiteral("color: %1;").arg(semanticColor(role).name());
}

// 危险操作按钮统一样式（遗忘 / 解绑确认共用），含 hover / pressed 状态。
inline QString dangerButtonStyle()
{
    const bool dark = isDarkPalette();
    const QColor bg = semanticColor(Role::DangerBackground);
    const QColor hover = dark ? bg.lighter(115) : bg.darker(110);
    const QColor pressed = dark ? bg.lighter(130) : bg.darker(120);
    return QStringLiteral(
               "QPushButton { background-color: %1; color: %2; border: none;"
               " border-radius: 8px; padding: 6px 14px; font-size: 11pt;"
               " font-weight: bold; }"
               "QPushButton:hover { background-color: %3; }"
               "QPushButton:pressed { background-color: %4; }")
        .arg(bg.name(), semanticColor(Role::DangerText).name(),
             hover.name(), pressed.name());
}

// 字号分级（ARCHITECTURE §7.2）：标题 14pt / 正文 11pt / 辅助 9pt。
namespace Font {
enum class Size { Title = 14, Body = 11, Caption = 9 };

inline QFont of(Size size, bool bold = false)
{
    QFont font;
    font.setPointSize(static_cast<int>(size));
    font.setBold(bold);
    return font;
}

inline QFont title() { return of(Size::Title, true); }
inline QFont body() { return of(Size::Body); }
inline QFont caption() { return of(Size::Caption); }
} // namespace Font

// 间距栅格（§7.3）：4 / 8 / 12 / 16。
namespace Spacing {
constexpr int XS = 4;
constexpr int S = 8;
constexpr int M = 12;
constexpr int L = 16;
constexpr int XL = 24;
} // namespace Spacing

// 圆角（§7.3）：窗口 12 / 卡片 8 / 按钮 8 / 气泡 10。
namespace Radius {
constexpr int Window = 12;
constexpr int Card = 8;
constexpr int Button = 8;
constexpr int Bubble = 10;
constexpr int Badge = 10;
constexpr int Small = 4;
} // namespace Radius

} // namespace ui

#endif // PIXIU_UI_TOKENS_H
