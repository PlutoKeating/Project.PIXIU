#include "app/ThemeService.h"

#include <QApplication>
#include <QColor>
#include <QLoggingCategory>
#include <QtGlobal>

#ifdef PIXIU_HAVE_KYSDK
#include <themeController.h>
#include <QGSettings/QGSettings>
#endif

Q_LOGGING_CATEGORY(lcTheme, "pixiu.theme")

namespace {

// ── PIXIU 设计系统调色（2026-08-10 侧边浮窗视觉统一）────────────
//
// 控件色一律取 palette 角色：浅色模式为“白 / 极浅灰 + 大量留白”，深色模式
// 为结构一致的深灰蓝变体。高亮色（Highlight）不在此处覆盖，始终跟随 UKUI
// 系统主题，保证“原生一致”不回归。

// 浅色：窗口极浅灰、内容白、输入/卡片浅灰填充，边框使用柔和 Mid。
QPalette lightPalette(const QPalette &base)
{
    QPalette p = base;
    p.setColor(QPalette::Window, QColor(0xf5, 0xf6, 0xf8));
    p.setColor(QPalette::WindowText, QColor(0x1f, 0x23, 0x29));
    p.setColor(QPalette::Base, QColor(0xff, 0xff, 0xff));
    p.setColor(QPalette::AlternateBase, QColor(0xed, 0xf0, 0xf4));
    p.setColor(QPalette::Text, QColor(0x1f, 0x23, 0x29));
    p.setColor(QPalette::Button, QColor(0xed, 0xf0, 0xf4));
    p.setColor(QPalette::ButtonText, QColor(0x1f, 0x23, 0x29));
    p.setColor(QPalette::Mid, QColor(0xd5, 0xda, 0xe1));
    p.setColor(QPalette::Midlight, QColor(0xe3, 0xe7, 0xec));
    p.setColor(QPalette::Light, QColor(0xff, 0xff, 0xff));
    p.setColor(QPalette::Dark, QColor(0xb6, 0xbc, 0xc6));
    p.setColor(QPalette::ToolTipBase, QColor(0xff, 0xff, 0xff));
    p.setColor(QPalette::ToolTipText, QColor(0x1f, 0x23, 0x29));
#if QT_VERSION >= QT_VERSION_CHECK(5, 12, 0)
    p.setColor(QPalette::PlaceholderText, QColor(0x98, 0x9f, 0xa9));
#endif
    return p;
}

// 深色：深灰蓝窗口、更深的内容底、浅灰蓝填充卡片；语义色由 UiTokens 提亮。
QPalette darkPalette()
{
    QPalette p;
    p.setColor(QPalette::Window, QColor(0x20, 0x23, 0x29));
    p.setColor(QPalette::WindowText, QColor(0xe2, 0xe6, 0xeb));
    p.setColor(QPalette::Base, QColor(0x19, 0x1c, 0x21));
    p.setColor(QPalette::AlternateBase, QColor(0x27, 0x2b, 0x33));
    p.setColor(QPalette::Text, QColor(0xe2, 0xe6, 0xeb));
    p.setColor(QPalette::Button, QColor(0x2d, 0x32, 0x3b));
    p.setColor(QPalette::ButtonText, QColor(0xe2, 0xe6, 0xeb));
    p.setColor(QPalette::Highlight, QColor(0x37, 0x90, 0xfa));
    p.setColor(QPalette::HighlightedText, QColor(0xff, 0xff, 0xff));
    p.setColor(QPalette::Mid, QColor(0x3b, 0x42, 0x4d));
    p.setColor(QPalette::Midlight, QColor(0x46, 0x4e, 0x5a));
    p.setColor(QPalette::Light, QColor(0x5a, 0x63, 0x70));
    p.setColor(QPalette::Dark, QColor(0x12, 0x14, 0x18));
    p.setColor(QPalette::ToolTipBase, QColor(0x2d, 0x32, 0x3b));
    p.setColor(QPalette::ToolTipText, QColor(0xe2, 0xe6, 0xeb));
#if QT_VERSION >= QT_VERSION_CHECK(5, 12, 0)
    p.setColor(QPalette::PlaceholderText, QColor(0x7b, 0x82, 0x8d));
#endif
    return p;
}

} // namespace

#ifdef PIXIU_HAVE_KYSDK
// ThemeController 非 QObject，changeTheme() 为虚函数：子类化以接收主题变化。
class ThemeService::KylinThemeController : public ThemeController
{
public:
    explicit KylinThemeController(ThemeService *service)
        : m_service(service)
    {
    }

    void changeTheme() override
    {
        if (m_service) {
            m_service->applyTheme();
        }
    }

private:
    ThemeService *m_service = nullptr;
};
#endif

ThemeService::ThemeService(QObject *parent)
    : QObject(parent)
{
}

bool ThemeService::start()
{
#ifdef PIXIU_HAVE_KYSDK
    if (m_controller) {
        return true;
    }

    // 记录系统浅色 Palette，供深色切回浅色时恢复。
    m_originalPalette = QApplication::palette();

    m_controller = new KylinThemeController(this);
    m_controller->initThemeStyle();
    // 本机库版本（kysdk-qtwidgets 2.3.1.0）中 initThemeStyle() 不会自动连接
    // 主题变化信号；按 Kylin 惯例直连其公开的 m_gsetting，过滤 styleName
    // 键（库内监听的键名为 camelCase）后触发 changeTheme()。
    if (m_controller->m_gsetting) {
        connect(m_controller->m_gsetting, &QGSettings::changed, this,
                [this](const QString &key) {
                    if (key == QStringLiteral("styleName")) {
                        m_controller->changeTheme();
                    }
                });
    } else {
        qCWarning(lcTheme) << "QGSettings unavailable; theme following disabled";
    }
    applyTheme();
    qCInfo(lcTheme) << "UKUI theme following enabled";
    return true;
#else
    // 降级路径（开发态 / 无 KYSDK）：仍应用 PIXIU 设计系统明暗调色，保证
    // 离屏渲染与开发截图与真实桌面观感一致；主题切换跟随能力由 KYSDK 提供，
    // 因此返回值保持 false（语义：无系统主题跟随）。
    m_originalPalette = QApplication::palette();
    applyTheme();
    qCInfo(lcTheme) << "theme following disabled; design-system palette applied";
    return false;
#endif
}

void ThemeService::applyTheme()
{
#ifdef PIXIU_HAVE_KYSDK
    // 本机 kysdk-qtwidgets 2.3.1.0 中 themeMode()/widgetTheme() 只在
    // initThemeStyle() 时缓存一次，运行期切换主题不会刷新缓存（运行时
    // 探针确认：ukui-dark -> ukui-light 后 themeMode() 仍返回 DarkTheme）。
    // 因此明暗判定改读 QGSettings 实时 styleName；styleName 缺失时回退
    // themeMode()（启动时缓存值）。
    bool dark = (ThemeController::themeMode() == DarkTheme);
    if (m_controller->m_gsetting) {
        const QString styleName =
            m_controller->m_gsetting->get(QStringLiteral("styleName")).toString();
        if (!styleName.isEmpty()) {
            dark = styleName.contains(QStringLiteral("dark"), Qt::CaseInsensitive)
                || styleName.contains(QStringLiteral("black"), Qt::CaseInsensitive)
                || styleName.contains(QStringLiteral("night"), Qt::CaseInsensitive);
        }
    }
    if (dark) {
        QApplication::setPalette(darkPalette());
        m_darkApplied = true;
        qCInfo(lcTheme) << "applied UKUI dark palette";
    } else {
        QApplication::setPalette(lightPalette(m_originalPalette));
        m_darkApplied = false;
        qCInfo(lcTheme) << "applied PIXIU light palette";
    }
#else
    // 降级路径：按当前 Palette 亮度判定明暗并应用设计系统调色。
    const bool dark =
        QApplication::palette().color(QPalette::Window).lightness() < 128;
    if (dark) {
        QApplication::setPalette(darkPalette());
    } else {
        QApplication::setPalette(lightPalette(m_originalPalette));
    }
    qCInfo(lcTheme) << "theme palette normalized (fallback mode)";
#endif

    // QSS 中的 palette(role) 在换肤时不会自动重新解析（实测：窗口自绘背景已
    // 跟随新 Palette，但 QSS 卡片/输入区/chip 仍冻结在旧主题色）。重设一次
    // 全局 stylesheet 强制 QStyleSheetStyle 对全部控件重新 polish，保证
    // 运行时明暗切换与启动直接进入对应主题的观感一致。
    const QString sheet = qApp->styleSheet();
    if (!sheet.isEmpty()) {
        qApp->setStyleSheet(QString());
        qApp->setStyleSheet(sheet);
    }
}

bool ThemeService::isAvailable() const
{
#ifdef PIXIU_HAVE_KYSDK
    return m_controller != nullptr;
#else
    return false;
#endif
}
