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
// 资产 browser_download_url 指回本地 server 的 /deb 与 /deb.sha256。
QByteArray releaseJson(const QString &base, const QString &tag)
{
    const QByteArray tagName = ("v" + tag).toUtf8();
    const QByteArray b = base.toUtf8();
    QByteArray j = R"({ "tag_name": ")"
        + tagName
        + R"(", "assets": [
          {"name":"pixiu_0.1.6-1_amd64.deb","browser_download_url":")"
        + b
        + R"(/deb"},
          {"name":"pixiu_0.1.6-1_amd64.deb.sha256","browser_download_url":")"
        + b + R"(/deb.sha256"} ]})";
    return j;
}

// .sha256 asset 内容形状："<hash>  <filename>"。
QByteArray shaOf(const QByteArray &data)
{
    return ui::sha256Hex(data) + "  pixiu_0.1.6-1_amd64.deb\n";
}

// 下载落盘的临时 deb 路径（与 UpgradeController 内部路径一致）。
QString tempDebPath()
{
    return QStandardPaths::writableLocation(QStandardPaths::TempLocation)
        + QStringLiteral("/pixiu-update.deb");
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
    void upgradeFinishedSuccessShowsManualRestart();
    void invalidSourceRejectedShowsInvalidSource();
    void cancelVisibleDuringDownloadAndCancels();

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
        return server;
    }
};

void TestCheckUpdateDialog::initTestCase()
{
    qRegisterMetaType<UpgradeController::State>("UpgradeController::State");
}

void TestCheckUpdateDialog::init()
{
    QCoreApplication::setApplicationVersion(QStringLiteral("0.1.5"));
}

void TestCheckUpdateDialog::cleanup()
{
    QFile::remove(tempDebPath());
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
    dialog.open();

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

    dialog.open();

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

    dialog.open();

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
    controller.setInstallRunner(
        [](const QString &, const QStringList &, std::function<void(int)>) {
            // 停在 Installing：不回调 onFinished，避免安装后状态机快速推进。
        });
    CheckUpdateDialog dialog(&controller);

    dialog.open();
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
    // 安装中取消按钮可见。
    QPushButton *cancel = dialog.findChild<QPushButton *>(
        QStringLiteral("cancelButton"));
    QVERIFY(cancel != nullptr);
    QVERIFY(cancel->isVisible());

    // 清理：取消中止在途流程，避免挂起事件循环阻塞测试退出。
    controller.cancel();
    QTRY_COMPARE(controller.state(), UpgradeController::State::Cancelled);
}

void TestCheckUpdateDialog::upgradeFinishedSuccessShowsManualRestart()
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
    CheckUpdateDialog dialog(&controller);

    dialog.open();
    QPushButton *upgrade = dialog.findChild<QPushButton *>(
        QStringLiteral("upgradeButton"));
    QVERIFY(upgrade != nullptr);
    QTRY_VERIFY(upgrade->isEnabled());
    upgrade->click();   // 下载 → 校验 → 安装 → Success

    QLabel *status = dialog.findChild<QLabel *>(
        QStringLiteral("updateStatusLabel"));
    QVERIFY(status != nullptr);
    QTRY_COMPARE(status->text(),
                 QStringLiteral("升级成功，请手动重启应用以生效"));
    QVERIFY(!upgrade->isEnabled());
    QVERIFY(!QFile::exists(tempDebPath()));   // 安装后清理临时 deb
}

void TestCheckUpdateDialog::invalidSourceRejectedShowsInvalidSource()
{
    // 无效下载源（http:// 非 allowlist）→ downloadAndInstall 拦截 →
    // Failed + 「更新源无效」，且不发起下载。
    const QByteArray deb = QByteArrayLiteral("deb");
    FakeServer *server = seedUpdatable(deb);
    const QString base = server->baseUrl();
    QByteArray json = R"({ "tag_name": "v0.1.6", "assets": [
        {"name":"pixiu_0.1.6-1_amd64.deb","browser_download_url":")"
        + QByteArrayLiteral("http://evil.example.com/deb") + R"("},
        {"name":"pixiu_0.1.6-1_amd64.deb.sha256","browser_download_url":")"
        + QByteArrayLiteral("http://evil.example.com/deb.sha256") + R"("} ]})";
    server->addJson("/releases/latest", json);

    QNetworkAccessManager net;
    UpgradeController controller(&net, QUrl(base + "/releases/latest"));
    CheckUpdateDialog dialog(&controller);   // 默认 validator（https+allowlist）

    dialog.open();
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

    dialog.open();
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
    QVERIFY(!QFile::exists(tempDebPath()));
}

QTEST_MAIN(TestCheckUpdateDialog)
#include "t_check_update_dialog.moc"
