#include <QDir>
#include <QFile>
#include <QHash>
#include <QHostAddress>
#include <QLabel>
#include <QNetworkAccessManager>
#include <QProgressBar>
#include <QPushButton>
#include <QSet>
#include <QSignalSpy>
#include <QStandardPaths>
#include <QTcpServer>
#include <QTcpSocket>
#include <QTest>

#include <functional>

#include "app/UpgradeController.h"
#include "widgets/CheckUpdateDialog.h"

// ─── 本地假 HTTP server（TCP 桩），仿 t_upgrade_controller / t_http_backend ───
// 以真实 QNetworkAccessManager 走全网络栈（不经 backend transport），路由按
// 请求路径返回：完整响应 / 404 / 立即断开（网络故障）/ 半包不封尾（挂起下载，
// 供取消测试）。ReleaseInfo.debUrl/shaUrl 由 release JSON 指回同一 server。
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

    void addRoute(const QString &path, int status, const QByteArray &ct,
                  const QByteArray &body)
    {
        m_routes.insert(path, Route{status, ct, body});
    }
    void addJson(const QString &path, const QByteArray &json)
    {
        addRoute(path, 200, "application/json", json);
    }
    // 接受连接后立即断开 → 客户端收到 RemoteHostClosedError（网络故障）。
    void addDrop(const QString &path) { m_drop.insert(path); }
    // 发送「头部 + 前 firstChunk 字节 / 完整为 body」后保持连接不关闭 →
    // 下载挂起在 Downloading，供取消测试。
    void addPartial(const QString &path, const QByteArray &body, int firstChunk)
    {
        m_partial.insert(path, body);
        m_partialChunk.insert(path, firstChunk);
    }

private:
    struct Route {
        int status;
        QByteArray ct;
        QByteArray body;
    };

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
        const QString p = QString::fromLatin1(path);
        if (m_drop.contains(p)) {
            socket->abort(); // 立即断开，模拟网络中断
            return;
        }
        if (m_partial.contains(p)) {
            const QByteArray body = m_partial.value(p);
            const int chunk = m_partialChunk.value(p, body.size());
            const QByteArray head =
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: application/octet-stream\r\n"
                "Content-Length: " + QByteArray::number(body.size()) +
                "\r\n"
                "Connection: close\r\n"
                "\r\n";
            socket->write(head);
            socket->write(body.left(chunk));
            socket->flush();
            return; // 不封尾：reply 保持 Downloading 未完成
        }
        const auto it = m_routes.constFind(p);
        if (it == m_routes.constEnd()) {
            const QByteArray resp =
                "HTTP/1.1 404 Not Found\r\n"
                "Content-Type: application/json\r\n"
                "Content-Length: 0\r\n"
                "Connection: close\r\n"
                "\r\n";
            socket->write(resp);
            socket->flush();
            socket->disconnectFromHost();
            return;
        }
        const Route &r = it.value();
        const QByteArray body = r.body;
        const QByteArray resp =
            "HTTP/1.1 " + QByteArray::number(r.status) +
            " OK\r\n"
            "Content-Type: " + r.ct +
            "\r\n"
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
    QHash<QString, Route> m_routes;
    QSet<QString> m_drop;
    QHash<QString, QByteArray> m_partial;
    QHash<QString, int> m_partialChunk;
};

namespace {

// release/latest JSON（与 UpgradeUtils::parseRelease 期望形状一致），
// 资产 browser_download_url 指回本地 server 的 deb、sha256 与独立签名。
QByteArray releaseJson(const QString &base, const QString &tag)
{
    const QByteArray tagName = ("v" + tag).toUtf8();
    const QByteArray b = base.toUtf8();
    const QByteArray arch = ui::debianArchitecture().toUtf8();
    QByteArray j = R"({ "tag_name": ")"
        + tagName
        + R"(", "assets": [
          {"name":"pixiu_0.1.6-1_)"
        + arch + R"(.deb","browser_download_url":")"
        + b
        + R"(/deb"},
          {"name":"pixiu_0.1.6-1_)"
        + arch + R"(.deb.sha256","browser_download_url":")"
        + b
        + R"(/deb.sha256"},
          {"name":"pixiu_0.1.6-1_)"
        + arch + R"(.deb.sha256.sig","browser_download_url":")"
        + b + R"(/deb.sha256.sig"} ]})";
    return j;
}

// .sha256 asset 内容形状："<hash>  <filename>"。
QByteArray shaOf(const QByteArray &data)
{
    return ui::sha256Hex(data) + "  pixiu_0.1.6-1_"
        + ui::debianArchitecture().toUtf8() + ".deb\n";
}

QStringList tempDebFiles()
{
    QDir directory(
        QStandardPaths::writableLocation(QStandardPaths::TempLocation));
    return directory.entryList(
        {QStringLiteral("pixiu-update-*.deb")}, QDir::Files);
}

void removeTempDebFiles()
{
    QDir directory(
        QStandardPaths::writableLocation(QStandardPaths::TempLocation));
    for (const QString &file : tempDebFiles()) {
        directory.remove(file);
    }
}

// 本地假 server 的下载源判定（http://127.0.0.1）。生产默认 validator 要求
// https + GitHub host allowlist，测试须放宽以走本地 TCP 桩。
bool acceptLocalSource(const QUrl &url)
{
    const QString host = url.host();
    return host == QLatin1String("127.0.0.1") || host == QLatin1String("localhost");
}

} // namespace

// CheckUpdateDialog 的「状态 → UI」契约测试：注入真实 UpgradeController ×
// 本地假 server + installRunner 替身，驱动状态机观察控件（不需真实网络）。
class TestCheckUpdateDialog : public QObject
{
    Q_OBJECT

private slots:
    void initTestCase();
    void init();
    void cleanup();

    void updatableEnablesUpgradeAndShowsRemoteVersion();
    void upToDateDisablesUpgradeAndShowsLatest();
    void networkFailureShowsCannotConnect();
    void progressUpdatesBarDuringDownload();
    void upgradeFinishedSuccessOffersControlledRestart();
    void invalidSourceRejectedShowsInvalidSource();
    void cancelVisibleDuringDownloadAndCancels();
    // U-3-1：陈旧缓存残留——先前 Updatable 后重查 UpToDate 不得回填旧版本；
    //        取消后重进 Downloading 不得回填旧百分比。
    void previousUpdatableThenUpToDateClearsStaleVersion();
    void cancelThenRedownloadResetsProgress();

private:
    // 部署一个「本地有新版 0.1.6 可升级」的假 server，返回该 server。
    FakeServer *seedUpdatable(const QByteArray &debContent,
                              const QString &tag = QStringLiteral("0.1.6"))
    {
        FakeServer *server = new FakeServer(this);
        if (!server->start()) {
            qFatal("FakeServer failed to start");
        }
        const QString base = server->baseUrl();
        server->addJson("/releases/latest", releaseJson(base, tag));
        server->addRoute("/deb", 200, "application/octet-stream", debContent);
        server->addRoute("/deb.sha256", 200, "text/plain", shaOf(debContent));
        server->addRoute("/deb.sha256.sig", 200,
                         "application/octet-stream", "test-signature");
        return server;
    }
};

void TestCheckUpdateDialog::initTestCase()
{
    qRegisterMetaType<UpgradeController::State>("UpgradeController::State");
    // moc 对嵌套枚举记录的类型名是「FailedReason」（非全限定），QSignalSpy
    // 按该名字段查 Metatype，注册名须与之匹配，否则 reason 参数无法被捕获。
    qRegisterMetaType<UpgradeController::FailedReason>("FailedReason");
}

void TestCheckUpdateDialog::init()
{
    QCoreApplication::setApplicationVersion(QStringLiteral("0.1.5"));
    removeTempDebFiles();
}

void TestCheckUpdateDialog::cleanup()
{
    removeTempDebFiles();
}

void TestCheckUpdateDialog::updatableEnablesUpgradeAndShowsRemoteVersion()
{
    const QByteArray deb = QByteArrayLiteral("fake-deb-payload-0123456789");
    FakeServer *server = seedUpdatable(deb);
    const QString base = server->baseUrl();

    QNetworkAccessManager net;
    UpgradeController controller(&net, QUrl(base + "/releases/latest"));
    controller.setSourceValidator(acceptLocalSource);
    CheckUpdateDialog dialog(&controller);

    // 打开对话框触发一次检查 → 假 server 返回新版 → Updatable。
    dialog.showAndCheck();

    QPushButton *upgrade = dialog.findChild<QPushButton *>(
        QStringLiteral("upgradeButton"));
    QVERIFY(upgrade != nullptr);
    QTRY_VERIFY(upgrade->isEnabled());
    QVERIFY(dialog.controller() == &controller);

    QLabel *remote = dialog.findChild<QLabel *>(
        QStringLiteral("remoteVersionLabel"));
    QVERIFY(remote != nullptr);
    QCOMPARE(remote->text(), QStringLiteral("远程最新版本 0.1.6"));
    QLabel *status = dialog.findChild<QLabel *>(
        QStringLiteral("updateStatusLabel"));
    QVERIFY(status != nullptr);
    QCOMPARE(status->text(), QStringLiteral("发现新版本，可一键升级"));
    QLabel *security = dialog.findChild<QLabel *>(
        QStringLiteral("updateSecurityHintLabel"));
    QVERIFY(security != nullptr);
    QVERIFY(security->text().contains(QStringLiteral("系统授权")));
    QVERIFY(security->text().contains(QStringLiteral("同步身份将被保留")));
}

void TestCheckUpdateDialog::upToDateDisablesUpgradeAndShowsLatest()
{
    // 本地与远端同为 0.1.6 → UpToDate：禁用升级 + 远程标签「已是最新」。
    QCoreApplication::setApplicationVersion(QStringLiteral("0.1.6"));
    FakeServer *server = seedUpdatable(QByteArrayLiteral("deb"), "0.1.6");
    const QString base = server->baseUrl();

    QNetworkAccessManager net;
    UpgradeController controller(&net, QUrl(base + "/releases/latest"));
    controller.setSourceValidator(acceptLocalSource);
    CheckUpdateDialog dialog(&controller);

    dialog.showAndCheck();

    // UpToDate（可能短暂经过 Checking）：以远程标签「已是最新」为权威断言。
    QLabel *remote = dialog.findChild<QLabel *>(
        QStringLiteral("remoteVersionLabel"));
    QVERIFY(remote != nullptr);
    QTRY_COMPARE(remote->text(), QStringLiteral("已是最新"));
    QPushButton *upgrade = dialog.findChild<QPushButton *>(
        QStringLiteral("upgradeButton"));
    QVERIFY(upgrade != nullptr);
    QVERIFY(!upgrade->isEnabled());
    QLabel *status = dialog.findChild<QLabel *>(
        QStringLiteral("updateStatusLabel"));
    QVERIFY(status != nullptr);
    QCOMPARE(status->text(), QStringLiteral("已是最新版本"));
}

void TestCheckUpdateDialog::networkFailureShowsCannotConnect()
{
    // /releases/latest 接受连接后立即断开 → 网络失败 → 远程标签显示
    // 「无法连接更新服务器」+ 升级禁用。
    FakeServer server;
    QVERIFY(server.start());
    server.addDrop("/releases/latest");

    QNetworkAccessManager net;
    UpgradeController controller(
        &net, QUrl(server.baseUrl() + "/releases/latest"));
    controller.setSourceValidator(acceptLocalSource);
    CheckUpdateDialog dialog(&controller);

    dialog.showAndCheck();

    QLabel *remote = dialog.findChild<QLabel *>(
        QStringLiteral("remoteVersionLabel"));
    QVERIFY(remote != nullptr);
    QTRY_COMPARE(remote->text(), QStringLiteral("无法连接更新服务器"));
    QPushButton *upgrade = dialog.findChild<QPushButton *>(
        QStringLiteral("upgradeButton"));
    QVERIFY(upgrade != nullptr);
    QVERIFY(!upgrade->isEnabled());
}

void TestCheckUpdateDialog::progressUpdatesBarDuringDownload()
{
    // 完整下载：进度推进到 100（progressChanged 更新进度条），随后校验/安装。
    const QByteArray body = QByteArrayLiteral("fake-deb-progress-payload");
    FakeServer *server = seedUpdatable(body);
    const QString base = server->baseUrl();

    QNetworkAccessManager net;
    UpgradeController controller(&net, QUrl(base + "/releases/latest"));
    controller.setSourceValidator(acceptLocalSource);
    std::function<void(int)> finishInstall;
    controller.setInstallRunner(
        [&finishInstall](const QString &, const QStringList &,
                         std::function<void(int)> onFinished) {
            finishInstall = std::move(onFinished);
        });
    CheckUpdateDialog dialog(&controller);

    dialog.showAndCheck();
    QPushButton *upgrade = dialog.findChild<QPushButton *>(
        QStringLiteral("upgradeButton"));
    QVERIFY(upgrade != nullptr);
    QTRY_VERIFY(upgrade->isEnabled());
    upgrade->click();   // 下载 → 校验 → 安装（停在 Installing）

    QProgressBar *bar = dialog.findChild<QProgressBar *>(
        QStringLiteral("updateProgressBar"));
    QVERIFY(bar != nullptr);
    // progressChanged(100) 在下载完成时推进进度条到 100。
    QTRY_COMPARE(bar->value(), 100);
    QLabel *status = dialog.findChild<QLabel *>(
        QStringLiteral("updateStatusLabel"));
    QVERIFY(status != nullptr);
    // 下载/校验/安装后停在 Installing（申请安装权限）。
    QTRY_COMPARE(status->text(), QStringLiteral("正在申请安装权限…"));
    QVERIFY(!upgrade->isEnabled());
    // 安装中禁止强制取消/关闭，避免杀死 dpkg 留下半配置包。
    QPushButton *cancel = dialog.findChild<QPushButton *>(
        QStringLiteral("cancelButton"));
    QPushButton *close = dialog.findChild<QPushButton *>(
        QStringLiteral("closeButton"));
    QVERIFY(cancel != nullptr);
    QVERIFY(close != nullptr);
    QVERIFY(!cancel->isVisible());
    QVERIFY(!close->isEnabled());
    dialog.reject();
    QVERIFY(dialog.isVisible());

    QVERIFY(bool(finishInstall));
    finishInstall(0);
    QTRY_COMPARE(controller.state(), UpgradeController::State::Success);
}

void TestCheckUpdateDialog::upgradeFinishedSuccessOffersControlledRestart()
{
    const QByteArray deb = QByteArrayLiteral("fake-deb-payload-0123456789");
    FakeServer *server = seedUpdatable(deb);
    const QString base = server->baseUrl();

    QNetworkAccessManager net;
    UpgradeController controller(&net, QUrl(base + "/releases/latest"));
    controller.setSourceValidator(acceptLocalSource);
    controller.setInstallRunner(
        [](const QString &, const QStringList &, std::function<void(int)> onFinished) {
            onFinished(0);   // 安装退出码 0 → Success
        });
    int restartCalls = 0;
    controller.setRestartRunnerForTest(
        [&restartCalls](const QString &, const QStringList &) {
            ++restartCalls;
            return true;
        });
    QSignalSpy restartSpy(&controller, &UpgradeController::restartScheduled);
    CheckUpdateDialog dialog(&controller);

    dialog.showAndCheck();
    QPushButton *upgrade = dialog.findChild<QPushButton *>(
        QStringLiteral("upgradeButton"));
    QVERIFY(upgrade != nullptr);
    QTRY_VERIFY(upgrade->isEnabled());
    upgrade->click();   // 下载 → 校验 → 安装 → Success

    QLabel *status = dialog.findChild<QLabel *>(
        QStringLiteral("updateStatusLabel"));
    QVERIFY(status != nullptr);
    QTRY_COMPARE(status->text(),
                 QStringLiteral("升级成功，请重启应用以使用新版本"));
    QVERIFY(!upgrade->isEnabled());
    QPushButton *close = dialog.findChild<QPushButton *>(
        QStringLiteral("closeButton"));
    QVERIFY(close != nullptr);
    QCOMPARE(close->text(), QStringLiteral("立即重启"));
    close->click();
    QCOMPARE(restartCalls, 1);
    QCOMPARE(restartSpy.count(), 1);
    QVERIFY(tempDebFiles().isEmpty());   // 安装后清理临时 deb
}

void TestCheckUpdateDialog::invalidSourceRejectedShowsInvalidSource()
{
    // 无效下载源（http:// 非 allowlist）→ downloadAndInstall 拦截 →
    // Failed + 「更新源无效」，且不发起下载。
    const QByteArray deb = QByteArrayLiteral("deb");
    FakeServer *server = seedUpdatable(deb);
    const QString base = server->baseUrl();
    const QByteArray arch = ui::debianArchitecture().toUtf8();
    QByteArray json = R"({ "tag_name": "v0.1.6", "assets": [
        {"name":"pixiu_0.1.6-1_)"
        + arch + R"(.deb","browser_download_url":")"
        + QByteArrayLiteral("http://evil.example.com/deb") + R"("},
        {"name":"pixiu_0.1.6-1_)"
        + arch + R"(.deb.sha256","browser_download_url":")"
        + QByteArrayLiteral("http://evil.example.com/deb.sha256") + R"("},
        {"name":"pixiu_0.1.6-1_)"
        + arch + R"(.deb.sha256.sig","browser_download_url":")"
        + QByteArrayLiteral("http://evil.example.com/deb.sha256.sig")
        + R"("} ]})";
    server->addJson("/releases/latest", json);

    QNetworkAccessManager net;
    UpgradeController controller(&net, QUrl(base + "/releases/latest"));
    CheckUpdateDialog dialog(&controller);   // 默认 validator（https+allowlist）

    dialog.showAndCheck();
    QPushButton *upgrade = dialog.findChild<QPushButton *>(
        QStringLiteral("upgradeButton"));
    QVERIFY(upgrade != nullptr);
    QTRY_VERIFY(upgrade->isEnabled());
    upgrade->click();

    QLabel *status = dialog.findChild<QLabel *>(
        QStringLiteral("updateStatusLabel"));
    QVERIFY(status != nullptr);
    QTRY_COMPARE(status->text(), QStringLiteral("更新源无效"));
    QVERIFY(!upgrade->isEnabled());
}

void TestCheckUpdateDialog::cancelVisibleDuringDownloadAndCancels()
{
    // 半包不封尾 → Downloading → 取消按钮可见、点击取消 → Cancelled。
    const QByteArray body = QByteArrayLiteral("large-deb-body-to-hang");
    FakeServer *server = seedUpdatable(body);
    const QString base = server->baseUrl();
    server->addPartial("/deb", body, 5);

    QNetworkAccessManager net;
    UpgradeController controller(&net, QUrl(base + "/releases/latest"));
    controller.setSourceValidator(acceptLocalSource);
    CheckUpdateDialog dialog(&controller);

    dialog.showAndCheck();
    QPushButton *upgrade = dialog.findChild<QPushButton *>(
        QStringLiteral("upgradeButton"));
    QVERIFY(upgrade != nullptr);
    QTRY_VERIFY(upgrade->isEnabled());
    upgrade->click();

    QPushButton *cancel = dialog.findChild<QPushButton *>(
        QStringLiteral("cancelButton"));
    QVERIFY(cancel != nullptr);
    QTRY_VERIFY(cancel->isVisible());

    cancel->click();
    QTRY_COMPARE(controller.state(), UpgradeController::State::Cancelled);
    QLabel *status = dialog.findChild<QLabel *>(
        QStringLiteral("updateStatusLabel"));
    QVERIFY(status != nullptr);
    QCOMPARE(status->text(), QStringLiteral("已取消"));
    QVERIFY(!cancel->isVisible());
    QVERIFY(tempDebFiles().isEmpty());
}

void TestCheckUpdateDialog::previousUpdatableThenUpToDateClearsStaleVersion()
{
    // U-3-1a：先前 Updatable（m_remoteVersion="0.1.6"）后重查 UpToDate——
    // 远程行不得被 onUpgradeFinished 据残留 m_remoteVersion 覆写回旧版本。
    // （修复前：状态显示「已是最新版本」，远程行却回填「远程最新版本 0.1.6」。）
    const QByteArray deb = QByteArrayLiteral("fake-deb-payload-0123456789");
    FakeServer *server = seedUpdatable(deb);   // 假 server 恒返回 0.1.6
    const QString base = server->baseUrl();

    QNetworkAccessManager net;
    UpgradeController controller(&net, QUrl(base + "/releases/latest"));
    controller.setSourceValidator(acceptLocalSource);
    CheckUpdateDialog dialog(&controller);

    // 首次检查（应用 0.1.5）→ Updatable，远程行显示旧版本 0.1.6。
    dialog.showAndCheck();
    QPushButton *upgrade = dialog.findChild<QPushButton *>(
        QStringLiteral("upgradeButton"));
    QVERIFY(upgrade != nullptr);
    QTRY_VERIFY(upgrade->isEnabled());
    QLabel *remote = dialog.findChild<QLabel *>(
        QStringLiteral("remoteVersionLabel"));
    QVERIFY(remote != nullptr);
    QTRY_COMPARE(remote->text(), QStringLiteral("远程最新版本 0.1.6"));

    // 应用升至 0.1.6 后重查 → UpToDate：远程行应为「已是最新」，而非旧版本。
    QCoreApplication::setApplicationVersion(QStringLiteral("0.1.6"));
    dialog.showAndCheck();
    QTRY_COMPARE(remote->text(), QStringLiteral("已是最新"));
    QTRY_VERIFY(!upgrade->isEnabled());
}

void TestCheckUpdateDialog::cancelThenRedownloadResetsProgress()
{
    // U-3-1b：完整下载把进度推进到 100 后，用户在 polkit 认证框取消；
    // 重查再进 Downloading 时进度条不得回填上次的旧百分比（应为 0）。
    // （修复前：m_progress 残留旧值 100，重进 Downloading setValue(m_progress)
    //   短暂显示「下载中…100%」。）
    const QByteArray deb = QByteArrayLiteral("fake-deb-body-0123456789");
    FakeServer *server = seedUpdatable(deb);
    const QString base = server->baseUrl();

    QNetworkAccessManager net;
    UpgradeController controller(&net, QUrl(base + "/releases/latest"));
    controller.setSourceValidator(acceptLocalSource);
    int installCalls = 0;
    controller.setInstallRunner(
        [&installCalls](const QString &, const QStringList &,
                        std::function<void(int)> onFinished) {
            ++installCalls;
            onFinished(126); // 模拟用户取消 polkit 认证
        });
    CheckUpdateDialog dialog(&controller);

    QProgressBar *bar = dialog.findChild<QProgressBar *>(
        QStringLiteral("updateProgressBar"));
    QVERIFY(bar != nullptr);
    QPushButton *upgrade = dialog.findChild<QPushButton *>(
        QStringLiteral("upgradeButton"));
    QVERIFY(upgrade != nullptr);

    dialog.showAndCheck();
    QTRY_VERIFY(upgrade->isEnabled());
    upgrade->click();                  // 下载 → 校验 → polkit 取消
    QTRY_COMPARE(bar->value(), 100);   // 进度已推进到 100（m_progress=100）
    QTRY_COMPARE(controller.state(), UpgradeController::State::Cancelled);
    QCOMPARE(installCalls, 1);

    // 重查 → 重进 Downloading：进度条应复位为 0（不闪上次旧值）。
    server->addPartial("/deb", deb, 5);
    dialog.showAndCheck();
    QTRY_VERIFY(upgrade->isEnabled());
    upgrade->click();
    QCOMPARE(bar->value(), 0);

    controller.cancel();               // 清理：中止在途流程
    QTRY_COMPARE(controller.state(), UpgradeController::State::Cancelled);
}

QTEST_MAIN(TestCheckUpdateDialog)
#include "t_check_update_dialog.moc"
