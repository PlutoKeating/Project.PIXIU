#ifndef PIXIU_THEME_SERVICE_H
#define PIXIU_THEME_SERVICE_H

#include <QObject>
#include <QPalette>

// 主题服务：跟随 UKUI 明暗主题切换并同步应用 QApplication Palette。
//
// 麒麟环境（PIXIU_HAVE_KYSDK）：基于 kysdk-qtwidgets ThemeController 监听
// org.ukui.style 主题变化；changeTheme() 时按 themeMode() 应用明暗 Palette。
// 浅色主题恢复启动时捕获的系统 Palette，深色主题应用 UKUI 深色近似值。
// 开发态/降级（无 KYSDK）：不监听系统主题，保持 Qt 默认 Palette 静态降级。
class ThemeService : public QObject
{
    Q_OBJECT

public:
    explicit ThemeService(QObject *parent = nullptr);

    // 启动主题跟随。返回 false 表示未激活（静态 Palette 降级，不报错）。
    bool start();

    // 按当前系统主题立即应用 Palette（start 与 ThemeController::changeTheme 复用）。
    void applyTheme();

    // 当前是否激活系统主题跟随。
    bool isAvailable() const;

private:
#ifdef PIXIU_HAVE_KYSDK
    class KylinThemeController;
    KylinThemeController *m_controller = nullptr;
#endif
    QPalette m_originalPalette;
    bool m_darkApplied = false;
};

#endif // PIXIU_THEME_SERVICE_H
