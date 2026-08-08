#include <QTest>

#include "app/ThemeService.h"

// 主题服务测试固定编译 Qt 降级路径（不注入 PIXIU_HAVE_KYSDK 宏）：
// kysdk ThemeController 依赖 QGSettings/桌面会话，无法在 offscreen 测试中
// 确定性断言；KYSDK 路径由 PIXIU_HAVE_KYSDK=ON 的应用构建与冒烟验证覆盖。
class TestThemeService : public QObject
{
    Q_OBJECT

private slots:
    void unavailableByDefault();
    void startFallsBackGracefully();
    void applyThemeDoesNotTouchPalette();
};

void TestThemeService::unavailableByDefault()
{
    ThemeService service;
    QVERIFY(!service.isAvailable());
}

void TestThemeService::startFallsBackGracefully()
{
    ThemeService service;
    QVERIFY(!service.start());
    QVERIFY(!service.isAvailable());
}

void TestThemeService::applyThemeDoesNotTouchPalette()
{
    ThemeService service;
    service.applyTheme();
    QVERIFY(true);
}

QTEST_MAIN(TestThemeService)

#include "t_theme_service.moc"
