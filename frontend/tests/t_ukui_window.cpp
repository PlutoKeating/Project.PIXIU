#include <QTest>

#include "app/UkuiWindow.h"

// 窗口辅助测试固定编译 Qt 降级路径（不注入 PIXIU_HAVE_KYSDK 宏）：
// KShadowHelper 依赖桌面合成器/窗口管理器，无法在 offscreen 测试中确定性
// 断言；KYSDK 路径由 PIXIU_HAVE_KYSDK=ON 的应用构建与冒烟验证覆盖。
class TestUkuiWindow : public QObject
{
    Q_OBJECT

private slots:
    void unavailableByDefault();
    void decorateFallsBackGracefully();
    void decorateAcceptsNullWidget();
};

void TestUkuiWindow::unavailableByDefault()
{
    QVERIFY(!pixiu::ukuiWindowAvailable());
}

void TestUkuiWindow::decorateFallsBackGracefully()
{
    QWidget window;
    pixiu::decorateUkuiWindow(&window);
    pixiu::decorateUkuiWindow(&window, 28);
    QVERIFY(true);
}

void TestUkuiWindow::decorateAcceptsNullWidget()
{
    pixiu::decorateUkuiWindow(nullptr);
    QVERIFY(true);
}

QTEST_MAIN(TestUkuiWindow)

#include "t_ukui_window.moc"
