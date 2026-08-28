#include <QAction>
#include <QCheckBox>
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
    // A-3 修复测试缝：控制 GET/PUT 回包时机与失败。
    bool failGet = false;     // GET 立即 errorOccurred（模拟启动离线）
    bool failPut = false;     // PUT 立即 errorOccurred（模拟上送失败）
    bool autoEchoGet = true;  // false 时 GET 响应入队、手动释放
    bool autoEchoPut = true;  // false 时 PUT 回声入队、手动释放
    int monitorConfigCalls = 0;
    int updateMonitorConfigCalls = 0;
    QList<QJsonObject> queuedGetResponses;
    QList<QJsonObject> queuedPutEchos;

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

    // GET /monitor/config：默认同步回包（直接连接下 start() 内即生效）；
    // autoEchoGet=false 时响应入队，由测试手动释放（模拟响应乱序到达）。
    void monitorConfig() override
    {
        ++monitorConfigCalls;
        if (failGet) {
            emit errorOccurred(QStringLiteral("NETWORK_ERROR"),
                               QStringLiteral("backend unreachable"),
                               QString());
            return;
        }
        const QJsonObject config{
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
        };
        if (autoEchoGet) {
            emit configResult(config);
        } else {
            queuedGetResponses.append(config);
        }
    }
    // PUT /monitor/config：默认回显提交体（模拟服务端归一化成功）；
    // autoEchoPut=false 时回声入队，由测试按序释放（模拟乱序回声）。
    void updateMonitorConfig(const QJsonObject &payload) override
    {
        ++updateMonitorConfigCalls;
        if (failPut) {
            emit errorOccurred(QStringLiteral("NETWORK_ERROR"),
                               QStringLiteral("backend unreachable"),
                               QString());
            return;
        }
        if (autoEchoPut) {
            emit configResult(payload);
        } else {
            queuedPutEchos.append(payload);
        }
    }
    void monitorLog(int, int) override {}

    // 手动释放排队中的 GET 响应 / PUT 回声（模拟响应乱序到达）。
    void flushNextGet()
    {
        if (!queuedGetResponses.isEmpty()) {
            emit configResult(queuedGetResponses.takeFirst());
        }
    }
    void flushNextPutEcho()
    {
        if (!queuedPutEchos.isEmpty()) {
            emit configResult(queuedPutEchos.takeFirst());
        }
    }
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
    void reconnectRepullsConfigWhenNotAuthoritative();
    void offlineHintShownWhenPanelCreatedWhileOffline();
    void outOfOrderPutEchoSkipped();
    void dirtyGetDoesNotOverwriteUserEdits();

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

    // 第二个 PixiuApp 的窗口与类级实例并存且均为无父顶层窗口：用
    // 「start/emit 前后差值」定位属于新实例的窗口，避免与类级窗口混淆。
    template <typename T>
    static QList<T *> newTopLevels(const QList<T *> &before)
    {
        QList<T *> found = topLevels<T>();
        for (T *w : before) {
            found.removeAll(w);
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

void TestAppNavigation::reconnectRepullsConfigWhenNotAuthoritative()
{
    // A-3 修复（断线恢复对账）：启动时 GET 失败（离线）→ 非远端权威；
    // 重连（Connected）后应重新拉取配置，断言 monitorConfig 调用次数 2。
    qputenv("USER", QStringLiteral("pixiu-nav-reconnect-%1")
                        .arg(QCoreApplication::applicationPid())
                        .toUtf8());
    {
        QSettings raw;
        raw.remove(QStringLiteral("app/monitor/enabled"));
        raw.remove(QStringLiteral("app/monitor/ever_enabled"));
        raw.sync();
    }
    FakeTransport *fake = new FakeTransport(this);
    fake->failGet = true;

    PixiuApp app;
    app.setTransportForTest(fake);
    QVERIFY(app.start());
    QCOMPARE(fake->monitorConfigCalls, 1);

    // 断线恢复：后端重新在线，重拉配置成功。
    fake->failGet = false;
    emit fake->connectionStateChanged(ConnectionState::Connected);
    QCOMPARE(fake->monitorConfigCalls, 2);

    MonitorController *controller = app.findChild<MonitorController *>();
    QVERIFY(controller != nullptr);
    // 重拉成功的远端配置已应用（enabled=false 覆盖本地）。
    QVERIFY(!controller->isEnabled());
    QVERIFY(controller->isSourceEnabled(MonitorSource::Directory));

    app.shutdown();
}

void TestAppNavigation::offlineHintShownWhenPanelCreatedWhileOffline()
{
    // A-3 修复（离线提示迟到/永不消失）：配置失败发生在面板创建之前时，
    // 之后打开面板也必须显示「离线，仅本地生效」。
    qputenv("USER", QStringLiteral("pixiu-nav-offline-%1")
                        .arg(QCoreApplication::applicationPid())
                        .toUtf8());
    {
        QSettings raw;
        raw.remove(QStringLiteral("app/monitor/enabled"));
        raw.remove(QStringLiteral("app/monitor/ever_enabled"));
        raw.sync();
    }
    FakeTransport *fake = new FakeTransport(this);
    fake->failGet = true;

    const auto ballsBefore = topLevels<FloatingBall>();
    PixiuApp app;
    app.setTransportForTest(fake);
    QVERIFY(app.start());   // 启动 GET 失败 → 非远端权威

    // 经悬浮球信号打开监控中心（面板此刻才创建）。
    FloatingBall *ball = newTopLevels(ballsBefore).value(0);
    QVERIFY(ball != nullptr);
    const auto centersBefore = topLevels<MonitorCenterDialog>();
    emit ball->monitorCenterRequested();

    MonitorCenterDialog *center =
        newTopLevels(centersBefore).value(0);
    QVERIFY(center != nullptr);
    QLabel *hint = center->findChild<QLabel *>(
        QStringLiteral("monitorOfflineHint"));
    QVERIFY(hint != nullptr);
    QVERIFY(hint->isVisible());
    QCOMPARE(hint->text(), QStringLiteral("离线，仅本地生效"));

    app.shutdown();
}

void TestAppNavigation::outOfOrderPutEchoSkipped()
{
    // A-3 修复（回声校验）：乱序旧 PUT 回声不得覆盖用户最新改动——
    // 先放行的旧回声（P1）与暂存载荷（P2）不匹配 → 跳过应用；
    // 匹配的新回声（P2）到达后才应用。
    qputenv("USER", QStringLiteral("pixiu-nav-echo-%1")
                        .arg(QCoreApplication::applicationPid())
                        .toUtf8());
    {
        QSettings raw;
        raw.remove(QStringLiteral("app/monitor/enabled"));
        raw.remove(QStringLiteral("app/monitor/ever_enabled"));
        raw.sync();
    }
    FakeTransport *fake = new FakeTransport(this);
    fake->autoEchoPut = false;   // PUT 回声入队、手动按序释放

    const auto ballsBefore = topLevels<FloatingBall>();
    PixiuApp app;
    app.setTransportForTest(fake);
    QVERIFY(app.start());   // 启动 GET 立即应用（远端权威）

    FloatingBall *ball = newTopLevels(ballsBefore).value(0);
    QVERIFY(ball != nullptr);
    const auto centersBefore = topLevels<MonitorCenterDialog>();
    emit ball->monitorCenterRequested();
    MonitorCenterDialog *center =
        newTopLevels(centersBefore).value(0);
    QVERIFY(center != nullptr);
    QCheckBox *master = center->findChild<QCheckBox *>(
        QStringLiteral("monitorMasterCheck"));
    QVERIFY(master != nullptr);
    MonitorController *controller = app.findChild<MonitorController *>();
    QVERIFY(controller != nullptr);

    // 改动 1：总闸开启 → PUT#1（P1，enabled=true）。
    master->setChecked(true);
    QTRY_COMPARE(fake->updateMonitorConfigCalls, 1);
    QCOMPARE(fake->queuedPutEchos.size(), 1);

    // 改动 2（去抖窗口外）：总闸关闭 → PUT#2（P2，enabled=false）。
    QTest::qWait(350);
    master->setChecked(false);
    QTRY_COMPARE(fake->updateMonitorConfigCalls, 2);
    QCOMPARE(fake->queuedPutEchos.size(), 2);

    // 乱序：先放行旧回声 P1 → 与暂存 P2 不匹配 → 跳过应用，
    // 用户最新改动（关闭）不被覆盖。
    fake->flushNextPutEcho();
    QVERIFY(!controller->isEnabled());
    QCOMPARE(fake->queuedPutEchos.size(), 1);   // 暂存仍在等匹配回声

    // 再放行新回声 P2 → 匹配 → 应用，暂存清空。
    fake->flushNextPutEcho();
    QVERIFY(!controller->isEnabled());
    QCOMPARE(fake->queuedPutEchos.size(), 0);

    app.shutdown();
}

void TestAppNavigation::dirtyGetDoesNotOverwriteUserEdits()
{
    // A-3 修复（读后写竞态）：用户本地改动期间到达的 GET 响应不得覆盖
    // 本地改动——PUT 失败（离线）后重连重拉，GET 到达时 dirty 仍为 true
    // → 跳过应用，仅更新远端权威标记。
    qputenv("USER", QStringLiteral("pixiu-nav-dirty-%1")
                        .arg(QCoreApplication::applicationPid())
                        .toUtf8());
    {
        QSettings raw;
        raw.remove(QStringLiteral("app/monitor/enabled"));
        raw.remove(QStringLiteral("app/monitor/ever_enabled"));
        raw.sync();
    }
    FakeTransport *fake = new FakeTransport(this);
    fake->failPut = true;   // PUT 上送失败 → 离线提示 + 非远端权威

    const auto ballsBefore = topLevels<FloatingBall>();
    PixiuApp app;
    app.setTransportForTest(fake);
    QVERIFY(app.start());   // 启动 GET 成功（远端权威）

    FloatingBall *ball = newTopLevels(ballsBefore).value(0);
    QVERIFY(ball != nullptr);
    const auto centersBefore = topLevels<MonitorCenterDialog>();
    emit ball->monitorCenterRequested();
    MonitorCenterDialog *center =
        newTopLevels(centersBefore).value(0);
    QVERIFY(center != nullptr);
    QCheckBox *master = center->findChild<QCheckBox *>(
        QStringLiteral("monitorMasterCheck"));
    QVERIFY(master != nullptr);
    MonitorController *controller = app.findChild<MonitorController *>();
    QVERIFY(controller != nullptr);

    // 用户改动：总闸开启 → PUT 失败 → 离线提示显示。
    master->setChecked(true);
    QTRY_COMPARE(fake->updateMonitorConfigCalls, 1);
    QLabel *hint = center->findChild<QLabel *>(
        QStringLiteral("monitorOfflineHint"));
    QVERIFY(hint != nullptr);
    QVERIFY(hint->isVisible());

    // 断线恢复：重连后重拉 GET（远端仍为旧值 enabled=false）。
    fake->failPut = false;
    fake->monitorEnabled = false;
    emit fake->connectionStateChanged(ConnectionState::Connected);
    QCOMPARE(fake->monitorConfigCalls, 2);

    // dirty 仍为 true：GET 不覆盖用户本地改动（enabled 保持 true）。
    QVERIFY(controller->isEnabled());

    app.shutdown();
}

QTEST_MAIN(TestAppNavigation)
#include "t_app_navigation.moc"
