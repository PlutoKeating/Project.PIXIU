#include <QAction>
#include <QCheckBox>
#include <QDialog>
#include <QGuiApplication>
#include <QHash>
#include <QHostAddress>
#include <QJsonArray>
#include <QJsonObject>
#include <QLabel>
#include <QListWidget>
#include <QNetworkAccessManager>
#include <QPushButton>
#include <QSettings>
#include <QTabWidget>
#include <QTcpServer>
#include <QTcpSocket>
#include <QTest>
#include <QTextBrowser>

#include "app/EventRouter.h"
#include "app/MonitorController.h"
#include "app/PixiuApp.h"
#include "app/PreferenceController.h"
#include "app/Severity.h"
#include "app/UpgradeController.h"
#include "app/UpgradeUtils.h"
#include "services/BackendTransport.h"
#include "services/BackendTypes.h"
#include "services/NotifyService.h"
#include "widgets/ChatWindow.h"
#include "widgets/CheckUpdateDialog.h"
#include "widgets/FloatingBall.h"
#include "widgets/ImportDialog.h"
#include "widgets/InfoDialog.h"
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
    // conflictDetected 高/缺省分流的「刷新列表」观测缝：统计 refresh 次数。
    // echoConflicts=true 时 listConflicts 立即回空数组，让 ConflictController
    // 的 m_inFlight 在途标记复位（否则第二次 refresh 被在途防重跳过）。
    bool echoConflicts = false;
    int listConflictsCalls = 0;
    void listConflicts() override
    {
        ++listConflictsCalls;
        if (echoConflicts) {
            emit conflictsResult(QJsonArray());
        }
    }
    void preferenceHistory(const QString &) override {}
    void promoteMemory(const QJsonObject &) override {}
    void pairDevice(const QJsonObject &) override {}
    ConnectionState connectionState() const override
    {
        return ConnectionState::Connected;
    }
    // WS 派生用：指向不存在地址即可，连接失败为异步且被容忍。
    QString baseUrl() const override
    {
        return QStringLiteral("ws://127.0.0.1:1");
    }

    // ── 同步管理测试缝（SN-6）──
    // 默认不回包（模拟后端静默）；需要回包的用例置 autoEcho* 并填充载荷。
    bool autoEchoPeers = false;        // listPeers → peersResult
    bool autoEchoSyncStatus = false;   // syncStatus → syncStatusResult
    bool autoEchoSettings = true;      // updateSyncSettings → 回显提交体
    QJsonArray peersPayload;
    QJsonObject syncStatusPayload;
    QJsonArray discoverPayload;
    QStringList revokePeerCalls;
    int discoverCalls = 0;
    QStringList requestPairingCalls;
    QList<QPair<QString, bool>> confirmPairingCalls;
    QList<QPair<bool, bool>> settingsCalls;

    void listPeers() override
    {
        if (autoEchoPeers) {
            emit peersResult(QJsonObject{{QStringLiteral("peers"), peersPayload}});
        }
    }
    void syncStatus() override
    {
        if (autoEchoSyncStatus) {
            emit syncStatusResult(syncStatusPayload);
        }
    }
    void revokePeer(const QString &peerId) override
    {
        revokePeerCalls.append(peerId);
        emit revokeResult(QJsonObject{
            {QStringLiteral("status"), QStringLiteral("revoked")},
            {QStringLiteral("peer_id"), peerId},
            {QStringLiteral("domain"), QStringLiteral("shared:home")}});
    }
    void discoverDevices() override
    {
        ++discoverCalls;
        emit devicesLoaded(QJsonObject{{QStringLiteral("devices"), discoverPayload}});
    }
    void requestPairing(const QString &targetId) override
    {
        requestPairingCalls.append(targetId);
    }
    void confirmPairing(const QString &requestId, bool accept) override
    {
        confirmPairingCalls.append(qMakePair(requestId, accept));
        emit pairConfirmResult(QJsonObject{
            {QStringLiteral("status"),
             accept ? QStringLiteral("accepted") : QStringLiteral("rejected")}});
    }
    void updateSyncSettings(bool enabled, bool paused) override
    {
        settingsCalls.append(qMakePair(enabled, paused));
        if (autoEchoSettings) {
            emit settingsResult(QJsonObject{
                {QStringLiteral("enabled"), enabled},
                {QStringLiteral("paused"), paused}});
        }
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

    // ── B4-3 递送层测试缝 ──
    // 默认不回包（模拟后端静默）；需要回包的用例置 autoEcho* 并填充载荷。
    bool autoEchoInsights = false;        // deliveryInsights → insightsResult
    bool autoEchoDigest = false;          // deliveryDigest → digestResult
    bool autoEchoPreferences = false;     // preferencesList → preferencesListResult
    QJsonArray insightsPayload;
    QJsonObject digestPayload;
    QJsonArray preferencesPayload;
    int insightsCalls = 0;
    int digestCalls = 0;
    int preferencesListCalls = 0;

    void deliveryInsights() override
    {
        ++insightsCalls;
        if (autoEchoInsights) {
            emit insightsResult(insightsPayload);
        }
    }
    void deliveryDigest() override
    {
        ++digestCalls;
        if (autoEchoDigest) {
            emit digestResult(digestPayload);
        }
    }
    void preferencesList(const QString &) override
    {
        ++preferencesListCalls;
        if (autoEchoPreferences) {
            emit preferencesListResult(preferencesPayload);
        }
    }

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

// 测试用通知服务：记录 notify 调用（title/body），供 F3-1 打扰分级断言。
// 经 PixiuApp::setNotifyServiceForTest 注入（与 setTransportForTest 同模式）。
class RecordingNotifyService : public NotifyService
{
public:
    explicit RecordingNotifyService(QObject *parent = nullptr)
        : NotifyService(parent)
    {
    }

    int notifyCalls = 0;
    QStringList titles;
    QStringList bodies;
    bool notify(const QString &title, const QString &body) override
    {
        ++notifyCalls;
        titles << title;
        bodies << body;
        return false;
    }
};

// ─── 本地假 HTTP server（TCP 桩）：仅供升级控制器「检查更新」使用 ───
// 以真实 QNetworkAccessManager 走全网络栈（不经 backend transport），
// /releases/latest 返回带新版 tag 的 release JSON → 控制器进入 Updatable。
class FakeServer : public QObject
{
    Q_OBJECT

public:
    explicit FakeServer(QObject *parent = nullptr)
        : QObject(parent)
    {
        m_server = new QTcpServer(this);
        connect(m_server, &QTcpServer::newConnection, this,
                &FakeServer::onNewConnection);
    }

    bool start() { return m_server->listen(QHostAddress::LocalHost); }
    quint16 port() const { return m_server->serverPort(); }
    QString baseUrl() const
    {
        return QStringLiteral("http://127.0.0.1:%1").arg(port());
    }
    void addJson(const QString &path, const QByteArray &json)
    {
        m_routes.insert(path, json);
    }

private:
    void onNewConnection()
    {
        while (m_server->hasPendingConnections()) {
            QTcpSocket *socket = m_server->nextPendingConnection();
            socket->setParent(m_server);
            connect(socket, &QTcpSocket::readyRead, this,
                    [this, socket]() {
                        while (socket->canReadLine()) {
                            const QByteArray line =
                                socket->readLine().trimmed();
                            if (line.startsWith("GET ")) {
                                handle(socket, line.split(' ').value(1));
                                return;
                            }
                        }
                    });
            connect(socket, &QTcpSocket::disconnected,
                    socket, &QTcpSocket::deleteLater);
        }
    }

    void handle(QTcpSocket *socket, const QByteArray &path)
    {
        const auto it = m_routes.constFind(QString::fromLatin1(path));
        if (it == m_routes.constEnd()) {
            const QByteArray resp =
                "HTTP/1.1 404 Not Found\r\n"
                "Content-Length: 0\r\n"
                "Connection: close\r\n"
                "\r\n";
            socket->write(resp);
            socket->flush();
            socket->disconnectFromHost();
            return;
        }
        const QByteArray body = it.value();
        const QByteArray resp =
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: application/json\r\n"
            "Content-Length: " + QByteArray::number(body.size()) +
            "\r\n"
            "Connection: close\r\n"
            "\r\n" +
            body;
        socket->write(resp);
        socket->flush();
        socket->disconnectFromHost();
    }

    QTcpServer *m_server = nullptr;
    QHash<QString, QByteArray> m_routes;
};

namespace {

// release/latest JSON（与 UpgradeUtils::parseRelease 期望形状一致），
// 资产 browser_download_url 指回本地 server（检查更新阶段不会真正下载）。
QByteArray upgradeReleaseJson(const QString &base, const QString &tag)
{
    const QByteArray tagName = ("v" + tag).toUtf8();
    const QByteArray b = base.toUtf8();
    const QByteArray version = tag.toUtf8();
    const QByteArray architecture = ui::debianArchitecture().toUtf8();
    QByteArray j = R"({ "tag_name": ")"
        + tagName
        + R"(", "assets": [
          {"name":"pixiu_)"
        + version + "-1_" + architecture + R"(.deb","browser_download_url":")"
        + b
        + R"(/deb"},
          {"name":"pixiu_)"
        + version + "-1_" + architecture
        + R"(.deb.sha256","browser_download_url":")"
        + b
        + R"(/deb.sha256"},
          {"name":"pixiu_)"
        + version + "-1_" + architecture
        + R"(.deb.sha256.sig","browser_download_url":")"
        + b + R"(/deb.sha256.sig"} ]})";
    return j;
}

bool acceptLocalSource(const QUrl &url)
{
    const QString host = url.host();
    return host == QLatin1String("127.0.0.1") || host == QLatin1String("localhost");
}

} // namespace

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
    void settingsOpensAboutTermsPrivacyAndUpdatePages();
    void remoteConfigOverridesControllerOnStart();
    void captureEventAppendsWhenCenterOpen();
    void reconnectRepullsConfigWhenNotAuthoritative();
    void offlineHintShownWhenPanelCreatedWhileOffline();
    void outOfOrderPutEchoSkipped();
    void dirtyGetDoesNotOverwriteUserEdits();
    void syncMasterSwitchDefaultOnAndGates();
    void syncDiscoverListRendersAndPairs();
    void leaveNetworkButtonShowsConfirmAndRevokesAll();
    void syncConflictBannerCountsAndJumps();
    void conflictSeverityDispatchesDisturbance();
    void severityParsingNormalizesCaseAndUnknown();
    void pairRequestDialogShowsAndConfirms();
    void insightsLoadedRenderIntoChatWindow();
    void relevanceReminderMatchesTopicAndSkipsUnrelated();
    void relevanceReminderDailyCap();
    void preferenceChangeNotifiesOnVersionBumpOnly();
    void digestEntryNotifiesSummary();

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
    // 注入假升级控制器（本地假 server），避免测试点击「检查更新」触发真实
    // GitHub 网络；父为测试对象，生命周期覆盖类级 m_app 的全部使用。
    FakeServer *m_upgradeServer = nullptr;
    QNetworkAccessManager *m_upgradeNetwork = nullptr;
    UpgradeController *m_upgradeController = nullptr;
};

void TestAppNavigation::initTestCase()
{
    // 与 main.cpp 相同的应用版本（PIXIU_VERSION 由 CMake 注入，单一事实源）：
    // 更新对话框展示当前版本，接线断言须与真实发布一致。
    QCoreApplication::setApplicationVersion(QStringLiteral(PIXIU_VERSION));
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

    // 注入假升级控制器（本地假 server）：避免设置对话框点「检查更新」触发
    // 真实 GitHub 网络。远端用固定的 9.9.9（x.y.z，且永远高于产品版本），
    // 保证检查更新进入 Updatable。parseRelease 只接受三段版本号。
    m_upgradeServer = new FakeServer(this);
    QVERIFY(m_upgradeServer->start());
    m_upgradeServer->addJson("/releases/latest",
                             upgradeReleaseJson(m_upgradeServer->baseUrl(),
                                                QStringLiteral("9.9.9")));
    m_upgradeNetwork = new QNetworkAccessManager(this);
    m_upgradeController = new UpgradeController(
        m_upgradeNetwork,
        QUrl(m_upgradeServer->baseUrl() + QStringLiteral("/releases/latest")),
        this);
    m_upgradeController->setSourceValidator(acceptLocalSource);
    m_app->setUpgradeControllerForTest(m_upgradeController);

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

void TestAppNavigation::settingsOpensAboutTermsPrivacyAndUpdatePages()
{
    // V-2：设置对话框四入口 → 各自懒创建并打开对应页面。About/T&C/Privacy
    // 为独立 InfoDialog 实例（防文案混杂），检查更新为 CheckUpdateDialog。
    clickChip("settingsChip");
    SettingsDialog *settings = topLevels<SettingsDialog>().first();

    // 关于 PIXIU：懒创建第一份 InfoDialog，标题正确。
    const auto aboutsBefore = topLevels<InfoDialog>();
    QPushButton *about = settings->findChild<QPushButton *>(
        QStringLiteral("aboutUsButton"));
    QVERIFY(about != nullptr);
    QTest::mouseClick(about, Qt::LeftButton);
    const auto abouts = newTopLevels(aboutsBefore);
    QCOMPARE(abouts.size(), 1);
    QTRY_VERIFY(abouts.first()->isVisible());
    QCOMPARE(abouts.first()->windowTitle(), QStringLiteral("关于 PIXIU"));

    // 服务条款：第二份独立 InfoDialog，文案为条款页关键词。
    const auto termsBefore = topLevels<InfoDialog>();
    QPushButton *terms = settings->findChild<QPushButton *>(
        QStringLiteral("termsButton"));
    QVERIFY(terms != nullptr);
    QTest::mouseClick(terms, Qt::LeftButton);
    const auto termsDialogs = newTopLevels(termsBefore);
    QCOMPARE(termsDialogs.size(), 1);
    QTRY_VERIFY(termsDialogs.first()->isVisible());
    QCOMPARE(termsDialogs.first()->windowTitle(), QStringLiteral("服务条款"));
    QTextBrowser *termsBrowser = termsDialogs.first()->findChild<QTextBrowser *>(
        QStringLiteral("infoTextBrowser"));
    QVERIFY(termsBrowser != nullptr);
    QVERIFY(termsBrowser->toPlainText().contains(QStringLiteral("参赛作品")));

    // 隐私政策：第三份独立 InfoDialog。
    const auto privacyBefore = topLevels<InfoDialog>();
    QPushButton *privacy = settings->findChild<QPushButton *>(
        QStringLiteral("privacyButton"));
    QVERIFY(privacy != nullptr);
    QTest::mouseClick(privacy, Qt::LeftButton);
    const auto privacyDialogs = newTopLevels(privacyBefore);
    QCOMPARE(privacyDialogs.size(), 1);
    QTRY_VERIFY(privacyDialogs.first()->isVisible());
    QCOMPARE(privacyDialogs.first()->windowTitle(), QStringLiteral("隐私政策"));

    // 检查更新：懒创建 CheckUpdateDialog，注入升级控制器；点击即触发检查，
    // 假 server 返回高于 PIXIU_VERSION 的版本 → Updatable → 一键升级可用。
    const auto updatesBefore = topLevels<CheckUpdateDialog>();
    QPushButton *update = settings->findChild<QPushButton *>(
        QStringLiteral("checkUpdateButton"));
    QVERIFY(update != nullptr);
    QTest::mouseClick(update, Qt::LeftButton);
    const auto updates = newTopLevels(updatesBefore);
    QCOMPARE(updates.size(), 1);
    QTRY_VERIFY(updates.first()->isVisible());
    // 注入的控制器非空（PixiuApp 接线成功），不触发真实网络。
    QVERIFY(updates.first()->controller() != nullptr);
    QLabel *current = updates.first()->findChild<QLabel *>(
        QStringLiteral("currentVersionLabel"));
    QVERIFY(current != nullptr);
    QVERIFY(current->text().contains(QCoreApplication::applicationVersion()));
    // Updatable：一键升级可用 + 远程最新版本展示。
    QPushButton *upgrade = updates.first()->findChild<QPushButton *>(
        QStringLiteral("upgradeButton"));
    QVERIFY(upgrade != nullptr);
    QTRY_VERIFY(upgrade->isEnabled());
    QLabel *remote = updates.first()->findChild<QLabel *>(
        QStringLiteral("remoteVersionLabel"));
    QVERIFY(remote != nullptr);
    QTRY_VERIFY(remote->text().contains(QStringLiteral("远程最新版本")));
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

void TestAppNavigation::syncMasterSwitchDefaultOnAndGates()
{
    // 同步 Tab 总开关：默认开、PUT /sync/settings 生效、off 禁用下级控件。
    qputenv("USER", QStringLiteral("pixiu-nav-sync-master-%1")
                        .arg(QCoreApplication::applicationPid()).toUtf8());
    FakeTransport *fake = new FakeTransport(this);
    fake->autoEchoSyncStatus = true;
    fake->syncStatusPayload = QJsonObject{
        {QStringLiteral("enabled"), true},
        {QStringLiteral("paused"), false},
        {QStringLiteral("domain"), QStringLiteral("shared:home")},
        {QStringLiteral("peers_online"), 1},
        {QStringLiteral("peers_total"), 2}};
    fake->autoEchoPeers = true;
    fake->peersPayload = QJsonArray{
        QJsonObject{{QStringLiteral("id"), QStringLiteral("dev_self")},
                    {QStringLiteral("name"), QStringLiteral("书房工作站")},
                    {QStringLiteral("is_self"), true},
                    {QStringLiteral("status"), QStringLiteral("ONLINE")}},
        QJsonObject{{QStringLiteral("id"), QStringLiteral("dev_guest")},
                    {QStringLiteral("name"), QStringLiteral("客厅一体机")},
                    {QStringLiteral("is_self"), false},
                    {QStringLiteral("status"), QStringLiteral("ONLINE")}}};

    const auto chatsBefore = topLevels<ChatWindow>();
    const auto panelsBefore = topLevels<MemoryPanel>();
    PixiuApp app;
    app.setTransportForTest(fake);
    QVERIFY(app.start());

    ChatWindow *chat = newTopLevels(chatsBefore).value(0);
    QVERIFY(chat != nullptr);
    emit chat->syncPanelRequested();

    MemoryPanel *panel = newTopLevels(panelsBefore).value(0);
    QVERIFY(panel != nullptr);
    QCheckBox *master = panel->findChild<QCheckBox *>(
        QStringLiteral("syncMasterSwitch"));
    QVERIFY(master != nullptr);
    // 总开关默认开（GET /sync/status.enabled=true 回填后仍为开）。
    QVERIFY(master->isChecked());

    // 关闭总开关 → PUT /sync/settings(enabled=false, paused 保持)。
    master->click();
    QCOMPARE(fake->settingsCalls.size(), 1);
    QCOMPARE(fake->settingsCalls.first().first, false);
    QCOMPARE(fake->settingsCalls.first().second, false);
    // PUT 回声回填开关。
    QVERIFY(!master->isChecked());

    // off 禁用下级控件：暂停开关 / 配对 / 退出网络 / 发现列表。
    QCheckBox *pause = panel->findChild<QCheckBox *>(
        QStringLiteral("syncPauseSwitch"));
    QPushButton *pair = panel->findChild<QPushButton *>(
        QStringLiteral("pairDeviceButton"));
    QPushButton *leave = panel->findChild<QPushButton *>(
        QStringLiteral("leaveNetworkButton"));
    QListWidget *discovered = panel->findChild<QListWidget *>(
        QStringLiteral("discoveredDeviceList"));
    QVERIFY(pause != nullptr);
    QVERIFY(pair != nullptr);
    QVERIFY(leave != nullptr);
    QVERIFY(discovered != nullptr);
    QVERIFY(!pause->isEnabled());
    QVERIFY(!pair->isEnabled());
    QVERIFY(!leave->isEnabled());
    QVERIFY(!discovered->isEnabled());

    app.shutdown();
}

void TestAppNavigation::syncDiscoverListRendersAndPairs()
{
    // 发现列表：切到同步 Tab 触发 discover；可配对设备渲染「配对」按钮并
    // 发起 requestPairing。
    qputenv("USER", QStringLiteral("pixiu-nav-sync-discover-%1")
                        .arg(QCoreApplication::applicationPid()).toUtf8());
    FakeTransport *fake = new FakeTransport(this);
    fake->autoEchoSyncStatus = true;
    fake->syncStatusPayload = QJsonObject{
        {QStringLiteral("enabled"), true},
        {QStringLiteral("paused"), false}};
    fake->discoverPayload = QJsonArray{
        QJsonObject{{QStringLiteral("device_id"), QStringLiteral("dev_alpha")},
                    {QStringLiteral("device_name"), QStringLiteral("Alpha 一体机")},
                    {QStringLiteral("addresses"), QJsonArray{QStringLiteral("192.168.1.10")}},
                    {QStringLiteral("pairable"), true},
                    {QStringLiteral("paired"), false}},
        QJsonObject{{QStringLiteral("device_id"), QStringLiteral("dev_beta")},
                    {QStringLiteral("device_name"), QStringLiteral("Beta 笔记本")},
                    {QStringLiteral("addresses"), QJsonArray{QStringLiteral("192.168.1.11")}},
                    {QStringLiteral("pairable"), false},
                    {QStringLiteral("paired"), false}}};

    const auto chatsBefore = topLevels<ChatWindow>();
    const auto panelsBefore = topLevels<MemoryPanel>();
    PixiuApp app;
    app.setTransportForTest(fake);
    QVERIFY(app.start());

    ChatWindow *chat = newTopLevels(chatsBefore).value(0);
    QVERIFY(chat != nullptr);
    emit chat->syncPanelRequested();

    MemoryPanel *panel = newTopLevels(panelsBefore).value(0);
    QVERIFY(panel != nullptr);
    // 切到同步 Tab 触发一次发现。
    QCOMPARE(fake->discoverCalls, 1);

    QListWidget *list = panel->findChild<QListWidget *>(
        QStringLiteral("discoveredDeviceList"));
    QVERIFY(list != nullptr);
    QCOMPARE(list->count(), 2);

    QWidget *row0 = list->itemWidget(list->item(0));
    QVERIFY(row0 != nullptr);
    QPushButton *pair = row0->findChild<QPushButton *>(
        QStringLiteral("discoverPairButton"));
    QVERIFY(pair != nullptr);
    QTest::mouseClick(pair, Qt::LeftButton);
    QCOMPARE(fake->requestPairingCalls.size(), 1);
    QCOMPARE(fake->requestPairingCalls.first(), QStringLiteral("dev_alpha"));

    // 不可配对设备不提供「配对」按钮。
    QWidget *row1 = list->itemWidget(list->item(1));
    QVERIFY(row1 != nullptr);
    QVERIFY(row1->findChild<QPushButton *>(QStringLiteral("discoverPairButton"))
            == nullptr);

    app.shutdown();
}

void TestAppNavigation::leaveNetworkButtonShowsConfirmAndRevokesAll()
{
    // 退出网络：确认框展示待解除台数；确认后逐台 revoke 全部非本机设备。
    qputenv("USER", QStringLiteral("pixiu-nav-sync-leave-%1")
                        .arg(QCoreApplication::applicationPid()).toUtf8());
    FakeTransport *fake = new FakeTransport(this);
    fake->autoEchoSyncStatus = true;
    fake->syncStatusPayload = QJsonObject{
        {QStringLiteral("enabled"), true},
        {QStringLiteral("paused"), false}};
    fake->autoEchoPeers = true;
    fake->peersPayload = QJsonArray{
        QJsonObject{{QStringLiteral("id"), QStringLiteral("dev_self")},
                    {QStringLiteral("name"), QStringLiteral("书房工作站")},
                    {QStringLiteral("is_self"), true},
                    {QStringLiteral("status"), QStringLiteral("ONLINE")}},
        QJsonObject{{QStringLiteral("id"), QStringLiteral("dev_guest1")},
                    {QStringLiteral("name"), QStringLiteral("客厅一体机")},
                    {QStringLiteral("is_self"), false},
                    {QStringLiteral("status"), QStringLiteral("ONLINE")}},
        QJsonObject{{QStringLiteral("id"), QStringLiteral("dev_guest2")},
                    {QStringLiteral("name"), QStringLiteral("卧室平板")},
                    {QStringLiteral("is_self"), false},
                    {QStringLiteral("status"), QStringLiteral("OFFLINE")}}};

    const auto chatsBefore = topLevels<ChatWindow>();
    const auto panelsBefore = topLevels<MemoryPanel>();
    PixiuApp app;
    app.setTransportForTest(fake);
    QVERIFY(app.start());

    ChatWindow *chat = newTopLevels(chatsBefore).value(0);
    QVERIFY(chat != nullptr);
    emit chat->syncPanelRequested();

    MemoryPanel *panel = newTopLevels(panelsBefore).value(0);
    QVERIFY(panel != nullptr);
    QPushButton *leave = panel->findChild<QPushButton *>(
        QStringLiteral("leaveNetworkButton"));
    QVERIFY(leave != nullptr);
    QVERIFY(leave->isEnabled());

    QTest::mouseClick(leave, Qt::LeftButton);
    QDialog *confirm = panel->findChild<QDialog *>(
        QStringLiteral("leaveConfirmDialog"));
    QVERIFY(confirm != nullptr);
    QVERIFY(confirm->isVisible());
    QLabel *text = confirm->findChild<QLabel *>(QStringLiteral("leaveConfirmText"));
    QVERIFY(text != nullptr);
    QVERIFY(text->text().contains(QStringLiteral("2")));

    QPushButton *confirmBtn = confirm->findChild<QPushButton *>(
        QStringLiteral("leaveConfirmButton"));
    QVERIFY(confirmBtn != nullptr);
    QTest::mouseClick(confirmBtn, Qt::LeftButton);

    // 逐台 revoke：非本机设备按序解绑，确认框关闭。
    QCOMPARE(fake->revokePeerCalls.size(), 2);
    QCOMPARE(fake->revokePeerCalls.at(0), QStringLiteral("dev_guest1"));
    QCOMPARE(fake->revokePeerCalls.at(1), QStringLiteral("dev_guest2"));
    QVERIFY(!confirm->isVisible());

    app.shutdown();
}

void TestAppNavigation::syncConflictBannerCountsAndJumps()
{
    // 冲突横幅：N>0 可见；点击跳转冲突 Tab；conflictDetected WS 计数 +1。
    // 用注入假 transport 的独立实例，避免真实后端的 conflicts 重算干扰。
    qputenv("USER", QStringLiteral("pixiu-nav-sync-banner-%1")
                        .arg(QCoreApplication::applicationPid()).toUtf8());
    FakeTransport *fake = new FakeTransport(this);

    const auto panelsBefore = topLevels<MemoryPanel>();
    PixiuApp app;
    app.setTransportForTest(fake);
    QVERIFY(app.start());

    MemoryPanel *panel = newTopLevels(panelsBefore).value(0);
    QVERIFY(panel != nullptr);
    QPushButton *banner = panel->findChild<QPushButton *>(
        QStringLiteral("syncConflictBanner"));
    QVERIFY(banner != nullptr);
    // 初始计数 0：横幅隐藏。
    QVERIFY(banner->isHidden());

    panel->setSyncConflictCount(2);
    QVERIFY(!banner->isHidden());
    QVERIFY(banner->text().contains(QStringLiteral("2")));

    QTabWidget *tabs = panel->findChild<QTabWidget *>();
    QVERIFY(tabs != nullptr);
    QTest::mouseClick(banner, Qt::LeftButton);
    QCOMPARE(tabs->currentIndex(), 1);   // 点击跳转冲突 Tab

    // conflictDetected WS → 计数 +1（FakeTransport 不回 conflicts，
    // 计数保持递增，不被重算覆盖）。
    EventRouter *router = app.findChild<EventRouter *>();
    QVERIFY(router != nullptr);
    emit router->conflictDetected(QStringLiteral("2026年4月家庭支出清单"),
                                  QStringLiteral("body.items[2].amount"),
                                  QStringLiteral("156"), QStringLiteral("186"),
                                  QStringLiteral("high"));
    QCOMPARE(panel->syncConflictCount(), 3);
    QVERIFY(!banner->isHidden());
    QVERIFY(banner->text().contains(QStringLiteral("3")));

    panel->setSyncConflictCount(0);
    QVERIFY(banner->isHidden());

    app.shutdown();
}

void TestAppNavigation::conflictSeverityDispatchesDisturbance()
{
    // F3-1：conflictDetected 按 severity 分流打扰级别——
    //   low    → 静默（无通知、角标不动、不切 Tab、不刷新），仅横幅计数 +1；
    //   medium → 温和通知（「记忆已更新」）+ 角标 +1，不切 Tab、不刷新；
    //   high / 缺省 → 现状全动作（「检测到记忆冲突」+ 角标 +1 + 刷新列表
    //                 + 面板可见时切冲突 Tab）。
    qputenv("USER", QStringLiteral("pixiu-nav-sev-%1")
                        .arg(QCoreApplication::applicationPid()).toUtf8());
    FakeTransport *fake = new FakeTransport(this);
    fake->echoConflicts = true;   // 刷新后立即回包，复位在途标记
    RecordingNotifyService *notify = new RecordingNotifyService(this);

    const auto panelsBefore = topLevels<MemoryPanel>();
    const auto ballsBefore = topLevels<FloatingBall>();
    PixiuApp app;
    app.setTransportForTest(fake);
    app.setNotifyServiceForTest(notify);
    QVERIFY(app.start());

    MemoryPanel *panel = newTopLevels(panelsBefore).value(0);
    QVERIFY(panel != nullptr);
    panel->show();   // 面板可见：high 分流才可能触发切 Tab。
    QTabWidget *tabs = panel->findChild<QTabWidget *>();
    QVERIFY(tabs != nullptr);
    FloatingBall *ball = newTopLevels(ballsBefore).value(0);
    QVERIFY(ball != nullptr);
    EventRouter *router = app.findChild<EventRouter *>();
    QVERIFY(router != nullptr);

    // start() 已拉取一次冲突列表。
    const int refreshBaseline = fake->listConflictsCalls;
    QVERIFY(refreshBaseline >= 1);

    // ── low：静默 ──
    tabs->setCurrentIndex(0);
    const int unreadBefore = ball->unreadCount();
    const int countBefore = panel->syncConflictCount();
    emit router->conflictDetected(QStringLiteral("支出清单"),
                                  QStringLiteral("body.items[0].amount"),
                                  QStringLiteral("1"), QStringLiteral("2"),
                                  QStringLiteral("low"));
    QCOMPARE(panel->syncConflictCount(), countBefore + 1);   // 仅内存计数
    QCOMPARE(ball->unreadCount(), unreadBefore);             // 角标不动
    QCOMPARE(tabs->currentIndex(), 0);                       // 不切 Tab
    QCOMPARE(fake->listConflictsCalls, refreshBaseline);     // 不刷新
    QCOMPARE(notify->notifyCalls, 0);                        // 不通知

    // ── medium：温和通知 + 角标，不切 Tab、不刷新 ──
    tabs->setCurrentIndex(0);
    emit router->conflictDetected(QStringLiteral("支出清单"),
                                  QStringLiteral("body.items[0].amount"),
                                  QStringLiteral("1"), QStringLiteral("2"),
                                  QStringLiteral("medium"));
    QCOMPARE(panel->syncConflictCount(), countBefore + 2);
    QCOMPARE(ball->unreadCount(), unreadBefore + 1);         // 角标 +1
    QCOMPARE(tabs->currentIndex(), 0);                       // 不切 Tab
    QCOMPARE(fake->listConflictsCalls, refreshBaseline);     // 不刷新
    QCOMPARE(notify->notifyCalls, 1);
    QCOMPARE(notify->titles.last(), QStringLiteral("记忆已更新"));
    QCOMPARE(notify->bodies.last(), QStringLiteral("支出清单"));

    // ── high：现状全动作（含刷新 + 切 Tab）──
    tabs->setCurrentIndex(0);
    emit router->conflictDetected(QStringLiteral("支出清单"),
                                  QStringLiteral("body.items[0].amount"),
                                  QStringLiteral("1"), QStringLiteral("2"),
                                  QStringLiteral("high"));
    QCOMPARE(notify->notifyCalls, 2);
    QCOMPARE(notify->titles.last(), QStringLiteral("检测到记忆冲突"));
    QCOMPARE(ball->unreadCount(), unreadBefore + 2);
    QCOMPARE(fake->listConflictsCalls, refreshBaseline + 1); // 刷新冲突列表
    QCOMPARE(tabs->currentIndex(), 1);                       // 切到冲突 Tab

    // ── 缺省（旧后端无 severity 帧）：按 high 全动作 ──
    tabs->setCurrentIndex(0);
    emit router->conflictDetected(QStringLiteral("支出清单"),
                                  QStringLiteral("body.items[0].amount"),
                                  QStringLiteral("1"), QStringLiteral("2"),
                                  QString());
    QCOMPARE(notify->notifyCalls, 3);
    QCOMPARE(notify->titles.last(), QStringLiteral("检测到记忆冲突"));
    QCOMPARE(tabs->currentIndex(), 1);                       // 切到冲突 Tab

    app.shutdown();
}

void TestAppNavigation::severityParsingNormalizesCaseAndUnknown()
{
    // F3-1 收编 Minor：ui::parseSeverity 是 severity→行为映射的单一事实来源
    // （PixiuApp 分流 / MemoryPanel 着色共用），比较大小写不敏感，
    // 未知/空一律回落 high（宁可打扰不漏报）。
    QCOMPARE(ui::parseSeverity(QStringLiteral("low")), ui::Severity::Low);
    QCOMPARE(ui::parseSeverity(QStringLiteral("LOW")), ui::Severity::Low);
    QCOMPARE(ui::parseSeverity(QStringLiteral("  Low ")), ui::Severity::Low);
    QCOMPARE(ui::parseSeverity(QStringLiteral("medium")), ui::Severity::Medium);
    QCOMPARE(ui::parseSeverity(QStringLiteral("MEDIUM")), ui::Severity::Medium);
    QCOMPARE(ui::parseSeverity(QStringLiteral("high")), ui::Severity::High);
    QCOMPARE(ui::parseSeverity(QStringLiteral("HIGH")), ui::Severity::High);
    QCOMPARE(ui::parseSeverity(QString()), ui::Severity::High);      // 缺省
    QCOMPARE(ui::parseSeverity(QStringLiteral("banana")), ui::Severity::High);
}

void TestAppNavigation::pairRequestDialogShowsAndConfirms()
{
    // pair_request WS → 配对确认对话框（设备名 + PIN）；确认/拒绝 →
    // confirmPairing(requestId, accept)。
    qputenv("USER", QStringLiteral("pixiu-nav-sync-pairreq-%1")
                        .arg(QCoreApplication::applicationPid()).toUtf8());
    FakeTransport *fake = new FakeTransport(this);

    const auto chatsBefore = topLevels<ChatWindow>();
    PixiuApp app;
    app.setTransportForTest(fake);
    QVERIFY(app.start());

    ChatWindow *chat = newTopLevels(chatsBefore).value(0);
    QVERIFY(chat != nullptr);
    EventRouter *router = app.findChild<EventRouter *>();
    QVERIFY(router != nullptr);

    // 入站配对请求：弹确认框，展示设备名与 PIN。
    emit router->pairingRequested(QJsonObject{
        {QStringLiteral("type"), QStringLiteral("INCOMING")},
        {QStringLiteral("request_id"), QStringLiteral("req_pair1")},
        {QStringLiteral("from_device_id"), QStringLiteral("dev_alpha")},
        {QStringLiteral("from_name"), QStringLiteral("Alpha 一体机")},
        {QStringLiteral("pin"), QStringLiteral("483920")},
        {QStringLiteral("expires_at"), 1756080060}});

    QDialog *dialog = chat->findChild<QDialog *>(
        QStringLiteral("pairRequestDialog"));
    QVERIFY(dialog != nullptr);
    QVERIFY(dialog->isVisible());
    QLabel *info = dialog->findChild<QLabel *>(
        QStringLiteral("pairRequestInfoLabel"));
    QVERIFY(info != nullptr);
    QVERIFY(info->text().contains(QStringLiteral("Alpha 一体机")));
    QLabel *pin = dialog->findChild<QLabel *>(
        QStringLiteral("pairRequestPinLabel"));
    QVERIFY(pin != nullptr);
    QVERIFY(pin->text().contains(QStringLiteral("483920")));

    // 确认 → confirmPairing(request_id, true)。
    QPushButton *accept = dialog->findChild<QPushButton *>(
        QStringLiteral("pairRequestAcceptButton"));
    QVERIFY(accept != nullptr);
    QTest::mouseClick(accept, Qt::LeftButton);
    QCOMPARE(fake->confirmPairingCalls.size(), 1);
    QCOMPARE(fake->confirmPairingCalls.first().first,
             QStringLiteral("req_pair1"));
    QCOMPARE(fake->confirmPairingCalls.first().second, true);
    QVERIFY(!dialog->isVisible());

    // 拒绝 → confirmPairing(request_id, false)。
    emit router->pairingRequested(QJsonObject{
        {QStringLiteral("type"), QStringLiteral("INCOMING")},
        {QStringLiteral("request_id"), QStringLiteral("req_pair2")},
        {QStringLiteral("from_device_id"), QStringLiteral("dev_beta")},
        {QStringLiteral("from_name"), QStringLiteral("Beta 笔记本")},
        {QStringLiteral("pin"), QStringLiteral("112233")},
        {QStringLiteral("expires_at"), 1756080120}});
    QPushButton *reject = dialog->findChild<QPushButton *>(
        QStringLiteral("pairRequestRejectButton"));
    QVERIFY(reject != nullptr);
    QTest::mouseClick(reject, Qt::LeftButton);
    QCOMPARE(fake->confirmPairingCalls.size(), 2);
    QCOMPARE(fake->confirmPairingCalls.at(1).first,
             QStringLiteral("req_pair2"));
    QCOMPARE(fake->confirmPairingCalls.at(1).second, false);

    app.shutdown();
}

void TestAppNavigation::insightsLoadedRenderIntoChatWindow()
{
    // B4-3：启动时 DeliveryController::loadInsights() → insightsLoaded →
    // ChatWindow::setInsights 渲染动态洞察卡。
    qputenv("USER", QStringLiteral("pixiu-nav-insights-%1")
                        .arg(QCoreApplication::applicationPid()).toUtf8());
    FakeTransport *fake = new FakeTransport(this);
    fake->autoEchoInsights = true;
    fake->insightsPayload = QJsonArray{
        QJsonObject{
            {QStringLiteral("title"), QStringLiteral("2026年4月家庭支出清单")},
            {QStringLiteral("summary"),
             QStringLiteral("2026年4月家庭支出清单：本月水电燃气共支出 434.50 元…")},
            {QStringLiteral("knowledge_id"), QStringLiteral("knw_1")},
            {QStringLiteral("score"), 0.94},
            {QStringLiteral("kind"), QStringLiteral("recent")}},
        QJsonObject{
            {QStringLiteral("title"), QStringLiteral("会议记录")},
            {QStringLiteral("summary"), QStringLiteral("会议记录：季度规划…")}}};

    const auto chatsBefore = topLevels<ChatWindow>();
    PixiuApp app;
    app.setTransportForTest(fake);
    QVERIFY(app.start());

    ChatWindow *chat = newTopLevels(chatsBefore).value(0);
    QVERIFY(chat != nullptr);
    QCOMPARE(fake->insightsCalls, 1);
    // 动态洞察卡已渲染；静态建议兜底 4 张保留。
    QCOMPARE(chat->findChildren<QPushButton *>(
                 QStringLiteral("insightCard")).size(), 2);
    QCOMPARE(chat->findChildren<QPushButton *>(
                 QStringLiteral("suggestionCard")).size(), 4);

    app.shutdown();
}

void TestAppNavigation::relevanceReminderMatchesTopicAndSkipsUnrelated()
{
    // B4-3：目录捕获且已入库时，文件名 token 与近期洞察 title token 交集
    // 命中 → 相关主题轻提醒；不同主题 / 非目录 / 非 ingested 不触发。
    qputenv("USER", QStringLiteral("pixiu-nav-rel-%1")
                        .arg(QCoreApplication::applicationPid()).toUtf8());
    FakeTransport *fake = new FakeTransport(this);
    fake->autoEchoInsights = true;
    fake->insightsPayload = QJsonArray{
        QJsonObject{
            {QStringLiteral("title"), QStringLiteral("2026年4月家庭支出清单")},
            {QStringLiteral("summary"), QStringLiteral("s")},
            {QStringLiteral("knowledge_id"), QStringLiteral("knw_1")}}};
    RecordingNotifyService *notify = new RecordingNotifyService(this);

    PixiuApp app;
    app.setTransportForTest(fake);
    app.setNotifyServiceForTest(notify);
    QVERIFY(app.start());

    EventRouter *router = app.findChild<EventRouter *>();
    QVERIFY(router != nullptr);
    const int baseline = notify->notifyCalls;
    QCOMPARE(baseline, 0);   // 启动路径不产生通知

    // 同主题：命中 → 轻提醒。
    emit router->captureEvent(QStringLiteral("directory"),
                              QStringLiteral("ingested"),
                              QStringLiteral("记住文件 2026年4月家庭支出清单.xlsx"),
                              1756080000);
    QCOMPARE(notify->notifyCalls, baseline + 1);
    QCOMPARE(notify->titles.last(), QStringLiteral("相关主题提醒"));
    QVERIFY(notify->bodies.last().contains(QStringLiteral("2026年4月家庭支出清单")));

    // 不同主题：不触发。
    emit router->captureEvent(QStringLiteral("directory"),
                              QStringLiteral("ingested"),
                              QStringLiteral("记住文件 会议记录.txt"),
                              1756080060);
    QCOMPARE(notify->notifyCalls, baseline + 1);

    // 非目录来源 / 非 ingested 状态：不触发。
    emit router->captureEvent(QStringLiteral("clipboard"),
                              QStringLiteral("ingested"),
                              QStringLiteral("记住剪贴板内容"),
                              1756080120);
    emit router->captureEvent(QStringLiteral("directory"),
                              QStringLiteral("ignored"),
                              QStringLiteral("忽略超大文件 x"),
                              1756080180);
    QCOMPARE(notify->notifyCalls, baseline + 1);

    app.shutdown();
}

void TestAppNavigation::relevanceReminderDailyCap()
{
    // B4-3：相关主题轻提醒每日上限 3，第 4 次同主题命中不再提醒。
    qputenv("USER", QStringLiteral("pixiu-nav-relcap-%1")
                        .arg(QCoreApplication::applicationPid()).toUtf8());
    FakeTransport *fake = new FakeTransport(this);
    fake->autoEchoInsights = true;
    fake->insightsPayload = QJsonArray{
        QJsonObject{
            {QStringLiteral("title"), QStringLiteral("2026年4月家庭支出清单")},
            {QStringLiteral("summary"), QStringLiteral("s")},
            {QStringLiteral("knowledge_id"), QStringLiteral("knw_1")}}};
    RecordingNotifyService *notify = new RecordingNotifyService(this);

    PixiuApp app;
    app.setTransportForTest(fake);
    app.setNotifyServiceForTest(notify);
    QVERIFY(app.start());

    EventRouter *router = app.findChild<EventRouter *>();
    QVERIFY(router != nullptr);

    for (int i = 0; i < 4; ++i) {
        emit router->captureEvent(
            QStringLiteral("directory"), QStringLiteral("ingested"),
            QStringLiteral("记住文件 2026年4月家庭支出清单-%1.txt").arg(i),
            1756080000 + i);
    }
    // 前 3 次命中提醒，第 4 次被每日上限截断。
    QCOMPARE(notify->notifyCalls, 3);

    app.shutdown();
}

void TestAppNavigation::preferenceChangeNotifiesOnVersionBumpOnly()
{
    // B4-3：preferencesList 版本对比——首次列表为基线（不提醒，避免首开
    // 面板通知风暴）；版本提升或基线后新增偏好 → 轻提醒一次；版本未变不
    // 重复提醒（不误报）。
    qputenv("USER", QStringLiteral("pixiu-nav-pref-%1")
                        .arg(QCoreApplication::applicationPid()).toUtf8());
    FakeTransport *fake = new FakeTransport(this);
    fake->autoEchoPreferences = true;
    RecordingNotifyService *notify = new RecordingNotifyService(this);

    PixiuApp app;
    app.setTransportForTest(fake);
    app.setNotifyServiceForTest(notify);
    QVERIFY(app.start());

    PreferenceController *pc = app.findChild<PreferenceController *>();
    QVERIFY(pc != nullptr);

    // 基线：首次列表不提醒。
    fake->preferencesPayload = QJsonArray{
        QJsonObject{
            {QStringLiteral("id"), QStringLiteral("pref_1")},
            {QStringLiteral("key"), QStringLiteral("output_style.compact")},
            {QStringLiteral("version"), 1},
            {QStringLiteral("scope"), QStringLiteral("user:local")}}};
    pc->loadList();
    QCOMPARE(notify->notifyCalls, 0);

    // 版本提升：提醒一次。
    fake->preferencesPayload = QJsonArray{
        QJsonObject{
            {QStringLiteral("id"), QStringLiteral("pref_1")},
            {QStringLiteral("key"), QStringLiteral("output_style.compact")},
            {QStringLiteral("version"), 2},
            {QStringLiteral("scope"), QStringLiteral("user:local")}}};
    pc->loadList();
    QCOMPARE(notify->notifyCalls, 1);
    QCOMPARE(notify->titles.last(), QStringLiteral("偏好提醒"));
    QCOMPARE(notify->bodies.last(),
             QStringLiteral("已学习您的偏好：output_style.compact"));

    // 版本未变：不重复提醒（不误报）。
    pc->loadList();
    QCOMPARE(notify->notifyCalls, 1);

    // 基线后新出现的偏好：提醒一次。
    fake->preferencesPayload = QJsonArray{
        QJsonObject{
            {QStringLiteral("id"), QStringLiteral("pref_1")},
            {QStringLiteral("key"), QStringLiteral("output_style.compact")},
            {QStringLiteral("version"), 2},
            {QStringLiteral("scope"), QStringLiteral("user:local")}},
        QJsonObject{
            {QStringLiteral("id"), QStringLiteral("pref_2")},
            {QStringLiteral("key"), QStringLiteral("security_policy.screen_lock")},
            {QStringLiteral("version"), 1},
            {QStringLiteral("scope"), QStringLiteral("user:local")}}};
    pc->loadList();
    QCOMPARE(notify->notifyCalls, 2);

    app.shutdown();
}

void TestAppNavigation::digestEntryNotifiesSummary()
{
    // B4-3：聊天窗「今日简报」建议卡 → digestRequested → DeliveryController
    // 拉取 GET /delivery/digest → 摘要经系统通知展示。
    qputenv("USER", QStringLiteral("pixiu-nav-digest-%1")
                        .arg(QCoreApplication::applicationPid()).toUtf8());
    FakeTransport *fake = new FakeTransport(this);
    fake->autoEchoDigest = true;
    fake->digestPayload = QJsonObject{
        {QStringLiteral("date"), QStringLiteral("2026-08-29")},
        {QStringLiteral("summary"),
         QStringLiteral("当日新增 2 条记忆（目录 2），另有 1 条敏感内容已隔离")}};
    RecordingNotifyService *notify = new RecordingNotifyService(this);

    const auto chatsBefore = topLevels<ChatWindow>();
    PixiuApp app;
    app.setTransportForTest(fake);
    app.setNotifyServiceForTest(notify);
    QVERIFY(app.start());

    ChatWindow *chat = newTopLevels(chatsBefore).value(0);
    QVERIFY(chat != nullptr);
    emit chat->digestRequested();
    QCOMPARE(fake->digestCalls, 1);
    QCOMPARE(notify->notifyCalls, 1);
    QCOMPARE(notify->titles.last(), QStringLiteral("今日简报"));
    QCOMPARE(notify->bodies.last(),
             QStringLiteral("当日新增 2 条记忆（目录 2），另有 1 条敏感内容已隔离"));

    app.shutdown();
}

QTEST_MAIN(TestAppNavigation)
#include "t_app_navigation.moc"
