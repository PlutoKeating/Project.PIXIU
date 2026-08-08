#include "app/ThemeService.h"

#include <QApplication>
#include <QColor>
#include <QLoggingCategory>

#ifdef PIXIU_HAVE_KYSDK
#include <themeController.h>
#endif

Q_LOGGING_CATEGORY(lcTheme, "pixiu.theme")

namespace {

#ifdef PIXIU_HAVE_KYSDK
// UKUI 深色主题（启典主题）近似色；浅色主题恢复系统 Palette，不强改。
QPalette darkPalette()
{
    QPalette p;
    p.setColor(QPalette::Window, QColor(0x2b, 0x2b, 0x2b));
    p.setColor(QPalette::WindowText, QColor(0xd6, 0xd6, 0xd6));
    p.setColor(QPalette::Base, QColor(0x22, 0x22, 0x22));
    p.setColor(QPalette::AlternateBase, QColor(0x30, 0x30, 0x30));
    p.setColor(QPalette::Text, QColor(0xd6, 0xd6, 0xd6));
    p.setColor(QPalette::Button, QColor(0x3a, 0x3a, 0x3a));
    p.setColor(QPalette::ButtonText, QColor(0xd6, 0xd6, 0xd6));
    p.setColor(QPalette::Highlight, QColor(0x37, 0x90, 0xfa));
    p.setColor(QPalette::HighlightedText, QColor(0xff, 0xff, 0xff));
    p.setColor(QPalette::ToolTipBase, QColor(0x3a, 0x3a, 0x3a));
    p.setColor(QPalette::ToolTipText, QColor(0xd6, 0xd6, 0xd6));
    return p;
}
#endif

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
    applyTheme();
    qCInfo(lcTheme) << "UKUI theme following enabled";
    return true;
#else
    qCInfo(lcTheme) << "theme following disabled; using Qt default palette";
    return false;
#endif
}

void ThemeService::applyTheme()
{
#ifdef PIXIU_HAVE_KYSDK
    const bool dark = (ThemeController::themeMode() == DarkTheme);
    if (dark) {
        QApplication::setPalette(darkPalette());
        m_darkApplied = true;
        qCInfo(lcTheme) << "applied UKUI dark palette";
    } else if (m_darkApplied) {
        QApplication::setPalette(m_originalPalette);
        m_darkApplied = false;
        qCInfo(lcTheme) << "restored system palette (light theme)";
    } else {
        qCInfo(lcTheme) << "light theme active; system palette already in use";
    }
#else
    // 降级路径：不修改 Palette，保持 Qt/UKUI 样式默认值。
    qCInfo(lcTheme) << "theme palette untouched (fallback mode)";
#endif
}

bool ThemeService::isAvailable() const
{
#ifdef PIXIU_HAVE_KYSDK
    return m_controller != nullptr;
#else
    return false;
#endif
}
