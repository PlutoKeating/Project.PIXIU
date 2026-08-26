#include <QAction>
#include <QGuiApplication>
#include <QPushButton>
#include <QTabWidget>
#include <QTest>

#include "app/MonitorController.h"
#include "app/PixiuApp.h"
#include "services/BackendTypes.h"
#include "widgets/ChatWindow.h"
#include "widgets/FloatingBall.h"
#include "widgets/ImportDialog.h"
#include "widgets/InputBar.h"
#include "widgets/MemoryPanel.h"
#include "widgets/MonitorCenterDialog.h"
#include "widgets/SettingsDialog.h"

// 端到端导航回归：聊天框输入区上方 chip 快捷入口（记忆/设置/导入/同步）
// 点击后必须真正打开对应窗口/Tab。防止 UI 重构只重建视觉控件、却把原有
// 功能入口的接线弄丢（本用例直接驱动 PixiuApp 全链路，而不是只测信号层）。
class TestAppNavigation : public QObject
{
    Q_OBJECT

private slots:
    void initTestCase();
    void cleanupTestCase();
    void memoryChipOpensMemoryPanel();
    void settingsChipOpensSettingsDialog();
    void syncChipOpensMemoryPanelSyncTab();
    void importChipOpensImportDialogWhenOnline();
    void importChipDisabledWhileOffline();
    void repeatedClickActivatesExistingWindow();
    void chipClickRespondsWhenWindowNotActive();
    void pauseToggleFromBallFlipsController();
    void settingsOpensMonitorCenter();

private:
    template <typename T>
    static QList<T *> topLevels()
    {
        QList<T *> found;
        const auto widgets = QApplication::topLevelWidgets();
        for (QWidget *w : widgets) {
            if (T *t = qobject_cast<T *>(w)) {
                found.append(t);
            }
        }
        return found;
    }

    ChatWindow *chatWindow() const;
    InputBar *inputBar() const;
    QPushButton *chip(const char *objectName) const;
    void clickChip(const char *objectName);

    PixiuApp *m_app = nullptr;
    ChatWindow *m_chatWindow = nullptr;
};

void TestAppNavigation::initTestCase()
{
    // 单实例守卫的 socket 以 USER 命名；测试里隔离 USER，避免与桌面上正在
    // 运行的 PIXIU 实例互抢主实例（不影响被测代码路径）。
    qputenv("USER", QStringLiteral("pixiu-nav-test-%1")
                        .arg(QCoreApplication::applicationPid())
                        .toUtf8());
    m_app = new PixiuApp();
    QVERIFY(m_app->start());

    m_chatWindow = chatWindow();
    QVERIFY(m_chatWindow != nullptr);
    // 加宽到所有 chip 都放得下的确定宽度（字体/主题不同会导致默认 380 宽
    // 下最后几个 chip 溢出隐藏），保证导航测试点击的是可见按钮。
    m_chatWindow->resize(560, 640);
    m_chatWindow->showAndFocus();
    QVERIFY(m_chatWindow->isChatVisible());
}

void TestAppNavigation::cleanupTestCase()
{
    if (m_app) {
        m_app->shutdown();
        delete m_app;
        m_app = nullptr;
    }
}

ChatWindow *TestAppNavigation::chatWindow() const
{
    const auto windows = topLevels<ChatWindow>();
    return windows.isEmpty() ? nullptr : windows.first();
}

InputBar *TestAppNavigation::inputBar() const
{
    return m_chatWindow ? m_chatWindow->findChild<InputBar *>() : nullptr;
}

QPushButton *TestAppNavigation::chip(const char *objectName) const
{
    InputBar *bar = inputBar();
    return bar ? bar->findChild<QPushButton *>(QLatin1String(objectName))
               : nullptr;
}

void TestAppNavigation::clickChip(const char *objectName)
{
    QPushButton *button = chip(objectName);
    QVERIFY(button != nullptr);
    QVERIFY(button->isVisible());
    QVERIFY(button->isEnabled());
    QTest::mouseClick(button, Qt::LeftButton);
}

void TestAppNavigation::memoryChipOpensMemoryPanel()
{
    const auto panelsBefore = topLevels<MemoryPanel>();
    QCOMPARE(panelsBefore.size(), 1);
    QVERIFY(!panelsBefore.first()->isVisible());
    clickChip("memoryChip");
    const auto panels = topLevels<MemoryPanel>();
    QCOMPARE(panels.size(), 1);
    QTRY_VERIFY(panels.first()->isVisible());
    // offscreen 平台不支持窗口激活（raise/activateWindow 为 no-op），
    // 仅在真实窗口系统下断言前置激活。
    if (QGuiApplication::platformName() != QStringLiteral("offscreen")) {
        QTRY_VERIFY(panels.first()->isActiveWindow());
    }
}

void TestAppNavigation::settingsChipOpensSettingsDialog()
{
    // SettingsDialog 为懒创建：首次点击前不得存在窗口实例。
    QVERIFY(topLevels<SettingsDialog>().isEmpty());
    clickChip("settingsChip");
    const auto dialogs = topLevels<SettingsDialog>();
    QCOMPARE(dialogs.size(), 1);
    QTRY_VERIFY(dialogs.first()->isVisible());
}

void TestAppNavigation::syncChipOpensMemoryPanelSyncTab()
{
    // 同步入口设计归属：进入记忆管理面板并直接切到“同步”Tab。
    clickChip("syncChip");
    const auto panels = topLevels<MemoryPanel>();
    QCOMPARE(panels.size(), 1);
    QTRY_VERIFY(panels.first()->isVisible());
    QTabWidget *tabs = panels.first()->findChild<QTabWidget *>();
    QVERIFY(tabs != nullptr);
    QCOMPARE(tabs->tabText(2), QStringLiteral("同步"));
    QCOMPARE(tabs->currentIndex(), 2);
}

void TestAppNavigation::importChipOpensImportDialogWhenOnline()
{
    // 录入依赖后端在线（与旧版 📎 入口语义一致）：在线时点击必须打开
    // 现有 ImportDialog，而不是无响应。
    m_chatWindow->setBackendState(ConnectionState::Connected);
    const auto dialogsBefore = topLevels<ImportDialog>();
    QCOMPARE(dialogsBefore.size(), 1);
    QVERIFY(!dialogsBefore.first()->isVisible());
    clickChip("importChip");
    const auto dialogs = topLevels<ImportDialog>();
    QCOMPARE(dialogs.size(), 1);
    QTRY_VERIFY(dialogs.first()->isVisible());
}

void TestAppNavigation::importChipDisabledWhileOffline()
{
    // 离线时录入入口与旧版行为一致：禁用（灰态），不伪造可点击的假入口。
    m_chatWindow->setBackendState(ConnectionState::Disconnected);
    QPushButton *import = chip("importChip");
    QVERIFY(import != nullptr);
    QVERIFY(!import->isEnabled());
}

void TestAppNavigation::repeatedClickActivatesExistingWindow()
{
    // 已存在的窗口再次点击应激活既有实例，而不是不断重复创建。
    clickChip("memoryChip");
    clickChip("memoryChip");
    QCOMPARE(topLevels<MemoryPanel>().size(), 1);
    clickChip("settingsChip");
    QCOMPARE(topLevels<SettingsDialog>().size(), 1);
}

void TestAppNavigation::chipClickRespondsWhenWindowNotActive()
{
    // 回归：主窗口「未激活」时，用户第一次直接点击快捷入口必须立即响应，
    // 不允许首击被当作“仅激活窗口”的点击而吞掉（真实桌面曾观察到首击不
    // 触发，需确认与焦点无关、且控件首击即可响应）。
    QWidget other;
    other.setObjectName(QStringLiteral("otherWindow"));
    other.resize(200, 120);
    other.show();
    other.activateWindow();
    QApplication::setActiveWindow(&other);
    QVERIFY(QApplication::activeWindow() != m_chatWindow);

    const auto panelsBefore = topLevels<MemoryPanel>();
    QVERIFY(!panelsBefore.isEmpty());
    // 前面的用例可能已打开面板；本用例关注「未激活窗口上的首击」，
    // 先确保面板处于关闭状态再点击。
    panelsBefore.first()->hide();
    QVERIFY(!panelsBefore.first()->isVisible());

    // 只点击一次：若首击被焦点逻辑吞掉，面板不会出现。
    clickChip("memoryChip");
    const auto panels = topLevels<MemoryPanel>();
    QCOMPARE(panels.size(), 1);
    QTRY_VERIFY(panels.first()->isVisible());
}

void TestAppNavigation::pauseToggleFromBallFlipsController()
{
    // 悬浮球菜单“暂停/继续监控”必须翻转控制器全局开关并刷新菜单文案。
    const auto balls = topLevels<FloatingBall>();
    QVERIFY(!balls.isEmpty());
    QAction *pause =
        balls.first()->findChild<QAction *>(
            QStringLiteral("pauseMonitorAction"));
    QVERIFY(pause != nullptr);

    MonitorController *controller =
        m_app->findChild<MonitorController *>();
    QVERIFY(controller != nullptr);
    const bool before = controller->isEnabled();
    pause->trigger();
    QCOMPARE(controller->isEnabled(), !before);
    QCOMPARE(pause->text(), !before ? QStringLiteral("暂停监控")
                                    : QStringLiteral("继续监控"));
    pause->trigger();
    QCOMPARE(controller->isEnabled(), before);
    QCOMPARE(pause->text(), before ? QStringLiteral("暂停监控")
                                   : QStringLiteral("继续监控"));
}

void TestAppNavigation::settingsOpensMonitorCenter()
{
    // 设置对话框中的“监控中心…”按钮打开监控中心面板。
    clickChip("settingsChip");
    SettingsDialog *settings = topLevels<SettingsDialog>().first();
    QPushButton *button = settings->findChild<QPushButton *>(
        QStringLiteral("openMonitorCenterButton"));
    QVERIFY(button != nullptr);
    QTest::mouseClick(button, Qt::LeftButton);
    QTRY_VERIFY(!topLevels<MonitorCenterDialog>().isEmpty());
    QTRY_VERIFY(topLevels<MonitorCenterDialog>().first()->isVisible());
}

QTEST_MAIN(TestAppNavigation)
#include "t_app_navigation.moc"
