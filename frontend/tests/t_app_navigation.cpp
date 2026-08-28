#include <QAction>
#include <QGuiApplication>
#include <QJsonArray>
#include <QJsonObject>
#include <QLabel>
#include <QListWidget>
#include <QPushButton>
#include <QSettings>
#include <QTabWidget>
#include <QTest>

#include "app/EventRouter.h"
#include "app/MonitorController.h"
#include "app/PixiuApp.h"
#include "services/BackendTransport.h"
#include "services/BackendTypes.h"
#include "widgets/ChatWindow.h"
#include "widgets/FloatingBall.h"
#include "widgets/ImportDialog.h"
#include "widgets/InputBar.h"
#include "widgets/MemoryPanel.h"
#include "widgets/MonitorCenterDialog.h"
#include "widgets/SettingsDialog.h"

// 测试用假 transport：仅实现 A-3 需要的 /monitor/config 回包，其余为 no-op。
// 经 PixiuApp::setTransportForTest 注入，避免依赖真实后端。
class FakeTransport : public BackendTransport
{
public:
    explicit FakeTransport(QObject *parent = nullptr)
        : BackendTransport(parent)
    {
    }

    bool monitorEnabled = false;

    void connectToBackend() override {}
    void disconnectFromBackend() override {}
    quint64 queryMemory(const QString &, const QJsonObject &) override
    {
        return 0;
    }
    void writeMemory(const QJsonObject &) override {}
    void forget(const QString &, bool) override {}
    void listConflicts() override {}
    void preferenceHistory(const QString &) override {}
    void promoteMemory(const QJsonObject &) override {}
    void pairDevice(const QJsonObject &) override {}
    void listPeers() override {}
    void syncStatus() override {}
    void revokePeer(const QString &) override {}
    ConnectionState connectionState() const override
    {
        return ConnectionState::Connected;
    }
    // WS 派生用：指向不存在地址即可，连接失败为异步且被容忍。
    QString baseUrl() const override
    {
        return QStringLiteral("ws://127.0.0.1:1");
    }

    // GET /monitor/config：同步回包（直接连接下 start() 内即生效）。
    void monitorConfig() override
    {
        emit configResult(QJsonObject{
            {QStringLiteral("enabled"), monitorEnabled},
            {QStringLiteral("sources"),
             QJsonObject{
                 {QStringLiteral("directory"), true},
                 {QStringLiteral("clipboard"), false},
                 {QStringLiteral("behavior"), true},
                 {QStringLiteral("screenshot"), false},
             }},
            {QStringLiteral("directories"),
             QJsonArray{QStringLiteral("/home/u/Downloads")}},
        });
    }
    // PUT /monitor/config：回显提交体（模拟服务端归一化成功）。
    void updateMonitorConfig(const QJsonObject &payload) override
    {
        emit configResult(payload);
    }
    void monitorLog(int, int) override {}
};

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
    void remoteConfigOverridesControllerOnStart();
    void captureEventAppendsWhenCenterOpen();

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
    // 监控徽标门控断言要求「从未启用过」的初始态：清除前序运行持久化的
    // 总闸与粘性标记（须在 PixiuApp::start() 构造 MonitorController 之前）。
    {
        QSettings raw;
        raw.remove(QStringLiteral("app/monitor/enabled"));
        raw.remove(QStringLiteral("app/monitor/ever_enabled"));
        raw.sync();
    }
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

    // 「⏸ 已暂停」徽标门控：仅在「曾开启过监控、当前关闭」时显示；
    // 从未启用过的用户（initTestCase 已清除粘性标记）界面保持干净。
    InputBar *bar = inputBar();
    QVERIFY(bar != nullptr);
    QLabel *badge = bar->findChild<QLabel *>(
        QStringLiteral("inputMonitorBadge"));
    QVERIFY(badge != nullptr);

    const bool before = controller->isEnabled();
    // 初始（未启用过）：不显示暂停提示。
    QVERIFY(!badge->isVisible());
    pause->trigger();
    QCOMPARE(controller->isEnabled(), !before);
    QCOMPARE(pause->text(), !before ? QStringLiteral("暂停监控")
                                    : QStringLiteral("继续监控"));
    // 开启中：同样不显示暂停徽标。
    QVERIFY(!badge->isVisible());
    pause->trigger();
    QCOMPARE(controller->isEnabled(), before);
    QCOMPARE(pause->text(), before ? QStringLiteral("暂停监控")
                                   : QStringLiteral("继续监控"));
    // 曾开启过 + 当前关闭：显示「⏸ 已暂停」徽标。
    QVERIFY(badge->isVisible());
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

void TestAppNavigation::remoteConfigOverridesControllerOnStart()
{
    // A-3：启动时 GET /monitor/config 成功 → 远端配置覆盖本地控制器状态
    // （enabled / 数据源开关 / 目录），并置 hasEverBeenEnabled。
    // 用独立 USER 的第二个 PixiuApp 实例（注入假 transport），
    // 避免与类级实例的单实例守卫互抢。
    qputenv("USER", QStringLiteral("pixiu-nav-remote-%1")
                        .arg(QCoreApplication::applicationPid())
                        .toUtf8());
    FakeTransport *fake = new FakeTransport(this);
    fake->monitorEnabled = true;

    PixiuApp app;
    app.setTransportForTest(fake);
    QVERIFY(app.start());

    MonitorController *controller = app.findChild<MonitorController *>();
    QVERIFY(controller != nullptr);
    // 远端 enabled=true 覆盖本地默认关闭态。
    QVERIFY(controller->isEnabled());
    QVERIFY(controller->isSourceEnabled(MonitorSource::Directory));
    QVERIFY(controller->isSourceEnabled(MonitorSource::Behavior));
    QVERIFY(!controller->isSourceEnabled(MonitorSource::Clipboard));
    QVERIFY(!controller->isSourceEnabled(MonitorSource::Screenshot));
    QCOMPARE(controller->directories(),
             QStringList{QStringLiteral("/home/u/Downloads")});
    // setEnabled(true) 顺带置位「曾开启过」粘性标记（远端覆盖的期望行为）。
    QVERIFY(controller->hasEverBeenEnabled());

    app.shutdown();
}

void TestAppNavigation::captureEventAppendsWhenCenterOpen()
{
    // A-3：监控中心打开时，WS capture_event 实时追加到活动记录列表。
    EventRouter *router = m_app->findChild<EventRouter *>();
    QVERIFY(router != nullptr);

    // 打开监控中心（设置 → 监控中心…）。
    clickChip("settingsChip");
    SettingsDialog *settings = topLevels<SettingsDialog>().first();
    QPushButton *button = settings->findChild<QPushButton *>(
        QStringLiteral("openMonitorCenterButton"));
    QVERIFY(button != nullptr);
    QTest::mouseClick(button, Qt::LeftButton);
    QTRY_VERIFY(!topLevels<MonitorCenterDialog>().isEmpty());
    MonitorCenterDialog *center = topLevels<MonitorCenterDialog>().first();
    QVERIFY(center->isVisible());

    QTabWidget *tabs = center->findChild<QTabWidget *>();
    QVERIFY(tabs != nullptr);
    tabs->setCurrentIndex(1);
    QListWidget *logList = center->findChild<QListWidget *>(
        QStringLiteral("monitorLogList"));
    QVERIFY(logList != nullptr);
    const int before = logList->count();

    emit router->captureEvent(QStringLiteral("clipboard"),
                              QStringLiteral("ingested"),
                              QStringLiteral("记住剪贴板内容"), 1756080000);
    QCOMPARE(logList->count(), before + 1);
}

QTEST_MAIN(TestAppNavigation)
#include "t_app_navigation.moc"
