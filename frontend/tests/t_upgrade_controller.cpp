#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QHash>
#include <QHostAddress>
#include <QNetworkAccessManager>
#include <QSet>
#include <QSignalSpy>
#include <QStandardPaths>
#include <QTcpServer>
#include <QTcpSocket>
#include <QTest>

#include <functional>

#include "app/UpgradeController.h"

// ─── 本地假 HTTP server（TCP 桩），仿 t_http_backend / t_contract_fixtures ───
// 以真实 QNetworkAccessManager 走全网络栈（不经 backend transport），路由按
// 请求路径返回：完整响应 / 404 / 立即断开（网络故障）/ 半包不封尾（挂起下载，
// 供取消测试）/ 302 重定向（模拟 GitHub browser_download_url 跳转）/ 接受后
// 挂起不响应（传输超时测试）。ReleaseInfo.debUrl/shaUrl 由 release JSON 指回
// 同一 server。
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
    // 下载挂起在 Downloading，供 cancel 测试。
    void addPartial(const QString &path, const QByteArray &body, int firstChunk)
    {
        m_partial.insert(path, body);
        m_partialChunk.insert(path, firstChunk);
    }
    void addPartialWithDeclaredLength(const QString &path,
                                      const QByteArray &firstChunk,
                                      qint64 declaredLength)
    {
        m_partial.insert(path, firstChunk);
        m_partialChunk.insert(path, firstChunk.size());
        m_declaredLength.insert(path, declaredLength);
    }
    // 接受请求后不发任何响应（保持连接开启）→ 客户端 transferTimeout 超时
    // （QNetworkReply::OperationCanceledError）。
    void addHang(const QString &path) { m_hang.insert(path); }
    // 302 重定向到 location（绝对或相对 URL）→ 模拟 GitHub browser_download_url
    // 302 → objects.githubusercontent.com。
    void addRedirect(const QString &path, const QString &location)
    {
        m_redirects.insert(path, location);
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
        if (m_hang.contains(p)) {
            return; // 接收请求但从不响应（保持连接开启）→ 客户端 transferTimeout
        }
        if (m_drop.contains(p)) {
            socket->abort(); // 立即断开，模拟网络中断
            return;
        }
        const auto rit = m_redirects.constFind(p);
        if (rit != m_redirects.constEnd()) {
            const QByteArray resp =
                "HTTP/1.1 302 Found\r\n"
                "Location: " + rit.value().toUtf8() + "\r\n"
                "Content-Length: 0\r\n"
                "Connection: close\r\n"
                "\r\n";
            socket->write(resp);
            socket->flush();
            socket->disconnectFromHost();
            return;
        }
        if (m_partial.contains(p)) {
            const QByteArray body = m_partial.value(p);
            const int chunk = m_partialChunk.value(p, body.size());
            const QByteArray head =
                "HTTP/1.1 200 OK\r\n"
                "Content-Type: application/octet-stream\r\n"
                "Content-Length: "
                + QByteArray::number(m_declaredLength.value(p, body.size()))
                +
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
    QHash<QString, qint64> m_declaredLength;
    QSet<QString> m_hang;
    QHash<QString, QString> m_redirects;
};

namespace {

// release/latest JSON（与 UpgradeUtils::parseRelease 期望形状一致），
// 资产 browser_download_url 指回本地 server 的 /deb 与 /deb.sha256。
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
        + b + R"(/deb.sha256"} ]})";
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

// UpgradeController：检查 / 版本比较 / 下载校验安装 / 取消的状态机契约测试。
// 网络走真实 QNetworkAccessManager × 本地 QTcpServer；安装用注入 runner 替身，
// 避免真实 pkexec/polkit。
class TestUpgradeController : public QObject
{
    Q_OBJECT

private slots:
    void initTestCase();
    void init();
    void cleanup();

    void initialStateIsIdle();
    void checkFindsUpdatable();
    void checkUpToDateWhenSameVersion();
    void checkUpToDateWhenRemoteOlder();
    void checkNetworkFailure();
    void checkHttpErrorIsFailure();
    void downloadAndInstallVerifiesAndInstalls();
    void downloadAndInstallVerifyFails();
    void installHandlesExitCodes();
    void cancelDuringDownload();
    void downloadIgnoredWhenNotUpdatable();
    void downloadFollowsRedirect();       // C1：GitHub 302 重定向须跟随
    void downloadRejectsUntrustedRedirect();
    void checkTimeoutFails();             // 传输超时 → Failed
    void invalidSourceRejected();         // 下载源非 https/非 allowlist → 更新源无效
    void installProcessStartFailureIsReported();
    void oversizedDownloadIsRejected();
    void oversizedChecksumIsRejected();

private:
    // 部署一个「本地有新版 0.1.6 可升级」的假 server，返回该 server 供路由。
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

void TestUpgradeController::initTestCase()
{
    qRegisterMetaType<UpgradeController::State>("UpgradeController::State");
    // moc 对嵌套枚举记录的类型名是「FailedReason」（非全限定），QSignalSpy
    // 按该名字段查 Metatype，注册名须与之匹配，否则 reason 参数无法被捕获。
    qRegisterMetaType<UpgradeController::FailedReason>("FailedReason");
}

void TestUpgradeController::init()
{
    QCoreApplication::setApplicationVersion(QStringLiteral("0.1.5"));
    removeTempDebFiles();
}

void TestUpgradeController::cleanup()
{
    removeTempDebFiles();
}

void TestUpgradeController::initialStateIsIdle()
{
    UpgradeController controller;
    QCOMPARE(controller.state(), UpgradeController::State::Idle);
}

void TestUpgradeController::checkFindsUpdatable()
{
    FakeServer server;
    QVERIFY(server.start());
    const QString base = server.baseUrl();
    server.addJson("/releases/latest", releaseJson(base, "0.1.6"));

    QNetworkAccessManager net;
    UpgradeController controller(&net, QUrl(base + "/releases/latest"));
    QSignalSpy versionSpy(&controller, &UpgradeController::remoteVersionFound);
    // stateChanged 的枚举参数不便于 QSignalSpy 取值，用 lambda 收集状态序列。
    QList<UpgradeController::State> seenStates;
    connect(&controller, &UpgradeController::stateChanged, this,
            [&seenStates](UpgradeController::State s) { seenStates.append(s); });

    controller.checkForUpdate();
    QCOMPARE(controller.state(), UpgradeController::State::Checking);

    QTRY_COMPARE(controller.state(), UpgradeController::State::Updatable);
    QCOMPARE(versionSpy.count(), 1);
    QCOMPARE(versionSpy.takeFirst().at(0).toString(),
             QStringLiteral("0.1.6"));

    QCOMPARE(seenStates.size(), 2);
    QCOMPARE(seenStates.at(0), UpgradeController::State::Checking);
    QCOMPARE(seenStates.at(1), UpgradeController::State::Updatable);
}

void TestUpgradeController::checkUpToDateWhenSameVersion()
{
    // 本地与远端同为 0.1.6 → UpToDate（compare == 0）。
    QCoreApplication::setApplicationVersion(QStringLiteral("0.1.6"));
    FakeServer server;
    QVERIFY(server.start());
    const QString base = server.baseUrl();
    server.addJson("/releases/latest", releaseJson(base, "0.1.6"));

    QNetworkAccessManager net;
    UpgradeController controller(&net, QUrl(base + "/releases/latest"));
    QSignalSpy finishedSpy(&controller, &UpgradeController::upgradeFinished);

    controller.checkForUpdate();
    QTRY_COMPARE(controller.state(), UpgradeController::State::UpToDate);
    QCOMPARE(finishedSpy.count(), 1);
    QCOMPARE(finishedSpy.at(0).at(0).toBool(), true);
    QCOMPARE(finishedSpy.at(0).at(1).toString(),
             QStringLiteral("已是最新版本"));
    QCOMPARE(finishedSpy.at(0).at(2).value<UpgradeController::FailedReason>(),
             UpgradeController::FailedReason::None);
}

void TestUpgradeController::checkUpToDateWhenRemoteOlder()
{
    // 本地 0.1.7 领先远端 0.1.6 → UpToDate（compare < 0）。
    QCoreApplication::setApplicationVersion(QStringLiteral("0.1.7"));
    FakeServer server;
    QVERIFY(server.start());
    server.addJson("/releases/latest", releaseJson(server.baseUrl(), "0.1.6"));

    QNetworkAccessManager net;
    UpgradeController controller(
        &net, QUrl(server.baseUrl() + "/releases/latest"));

    controller.checkForUpdate();
    QTRY_COMPARE(controller.state(), UpgradeController::State::UpToDate);
}

void TestUpgradeController::checkNetworkFailure()
{
    // server 接受连接后立即断开 → 网络错误 → Failed + 连接失败文案。
    FakeServer server;
    QVERIFY(server.start());
    server.addDrop("/drop");

    QNetworkAccessManager net;
    UpgradeController controller(&net, QUrl(server.baseUrl() + "/drop"));
    QSignalSpy finishedSpy(&controller, &UpgradeController::upgradeFinished);

    controller.checkForUpdate();
    QTRY_COMPARE(controller.state(), UpgradeController::State::Failed);
    QCOMPARE(finishedSpy.count(), 1);
    QCOMPARE(finishedSpy.at(0).at(0).toBool(), false);
    QCOMPARE(finishedSpy.at(0).at(1).toString(),
             QStringLiteral("无法连接更新服务器"));
    QCOMPARE(finishedSpy.at(0).at(2).value<UpgradeController::FailedReason>(),
             UpgradeController::FailedReason::Network);
}

void TestUpgradeController::checkHttpErrorIsFailure()
{
    // 未注册路径 → server 返回 404 → Failed + 连接失败文案。
    FakeServer server;
    QVERIFY(server.start());

    QNetworkAccessManager net;
    UpgradeController controller(
        &net, QUrl(server.baseUrl() + "/missing"));
    QSignalSpy finishedSpy(&controller, &UpgradeController::upgradeFinished);

    controller.checkForUpdate();
    QTRY_COMPARE(controller.state(), UpgradeController::State::Failed);
    QCOMPARE(finishedSpy.count(), 1);
    QCOMPARE(finishedSpy.at(0).at(0).toBool(), false);
    QCOMPARE(finishedSpy.at(0).at(1).toString(),
             QStringLiteral("无法连接更新服务器"));
    QCOMPARE(finishedSpy.at(0).at(2).value<UpgradeController::FailedReason>(),
             UpgradeController::FailedReason::Network);
}

void TestUpgradeController::downloadAndInstallVerifiesAndInstalls()
{
    const QByteArray deb = QByteArrayLiteral("fake-deb-payload-0123456789");
    FakeServer *server = seedUpdatable(deb);
    const QString base = server->baseUrl();

    QNetworkAccessManager net;
    UpgradeController controller(&net, QUrl(base + "/releases/latest"));
    // 本地假 server 用 http://127.0.0.1（非生产 allowlist），放宽下载源判定。
    controller.setSourceValidator(acceptLocalSource);
    QSignalSpy progressSpy(&controller, &UpgradeController::progressChanged);
    QSignalSpy finishedSpy(&controller, &UpgradeController::upgradeFinished);
    QList<UpgradeController::State> seen;
    connect(&controller, &UpgradeController::stateChanged, this,
            [&seen](UpgradeController::State s) { seen.append(s); });

    QString installProgram;
    QStringList installArgs;
    int installExit = 0;
    controller.setInstallRunner(
        [&](const QString &program, const QStringList &args,
            std::function<void(int)> onFinished) {
            installProgram = program;
            installArgs = args;
            onFinished(installExit);
        });

    controller.checkForUpdate();
    QTRY_COMPARE(controller.state(), UpgradeController::State::Updatable);
    controller.downloadAndInstall();

    // 下载 → 校验 → 安装（注入 runner 退出码 0）→ Success。
    QTRY_COMPARE(controller.state(), UpgradeController::State::Success);

    QCOMPARE(installProgram, QStringLiteral("/usr/bin/pkexec"));
    QCOMPARE(installArgs.size(), 3);
    QCOMPARE(installArgs.at(0),
             QStringLiteral("/usr/lib/pixiu/install-update"));
    QVERIFY(QFileInfo(installArgs.at(1)).fileName().startsWith(
        QStringLiteral("pixiu-update-")));
    QCOMPARE(installArgs.at(2),
             QString::fromLatin1(ui::sha256Hex(deb)));

    QVERIFY(progressSpy.count() > 0);
    QCOMPARE(progressSpy.last().at(0).toInt(), 100);

    QCOMPARE(finishedSpy.count(), 1);
    QCOMPARE(finishedSpy.at(0).at(0).toBool(), true);
    QCOMPARE(finishedSpy.at(0).at(1).toString(),
             QStringLiteral("升级成功，请手动重启应用以生效"));
    QCOMPARE(finishedSpy.at(0).at(2).value<UpgradeController::FailedReason>(),
             UpgradeController::FailedReason::None);

    // 状态机曾经过 Downloading/Verifying/Installing。
    QVERIFY(seen.contains(UpgradeController::State::Downloading));
    QVERIFY(seen.contains(UpgradeController::State::Verifying));
    QVERIFY(seen.contains(UpgradeController::State::Installing));

    // 安装完成后临时 deb 清理。
    QVERIFY(!QFile::exists(installArgs.at(1)));
}

void TestUpgradeController::downloadAndInstallVerifyFails()
{
    const QByteArray deb = QByteArrayLiteral("fake-deb-payload-ABCDEF");
    FakeServer *server = seedUpdatable(deb);
    const QString base = server->baseUrl();
    // 覆盖 sha256 资产为「错误摘要」→ 校验不通过。
    const QString wrongHash = QStringLiteral(
        "0000000000000000000000000000000000000000000000000000000000000000");
    server->addRoute("/deb.sha256", 200, "text/plain",
                     (wrongHash + "  pixiu_0.1.6-1_amd64.deb\n").toUtf8());

    QNetworkAccessManager net;
    UpgradeController controller(&net, QUrl(base + "/releases/latest"));
    controller.setSourceValidator(acceptLocalSource);
    QSignalSpy finishedSpy(&controller, &UpgradeController::upgradeFinished);
    int runnerCalls = 0;
    controller.setInstallRunner(
        [&](const QString &, const QStringList &,
            std::function<void(int)>) { ++runnerCalls; });

    controller.checkForUpdate();
    QTRY_COMPARE(controller.state(), UpgradeController::State::Updatable);
    controller.downloadAndInstall();

    QTRY_COMPARE(controller.state(), UpgradeController::State::Failed);
    QCOMPARE(finishedSpy.count(), 1);
    QCOMPARE(finishedSpy.at(0).at(0).toBool(), false);
    QCOMPARE(finishedSpy.at(0).at(1).toString(),
             QStringLiteral("校验失败，已中止"));
    QCOMPARE(finishedSpy.at(0).at(2).value<UpgradeController::FailedReason>(),
             UpgradeController::FailedReason::Verify);
    QCOMPARE(runnerCalls, 0); // 校验失败未进入安装
    QVERIFY(tempDebFiles().isEmpty()); // 临时 deb 清理
}

void TestUpgradeController::installHandlesExitCodes()
{
    struct Case {
        int exitCode;
        UpgradeController::State expected;
        const char *message;
    };
    const Case cases[] = {
        {0, UpgradeController::State::Success, "升级成功，请手动重启应用以生效"},
        {126, UpgradeController::State::Cancelled, "已取消，升级未执行"},
        {127, UpgradeController::State::Cancelled, "已取消，升级未执行"},
        {123, UpgradeController::State::Failed, "升级失败，请检查系统日志"},
    };

    for (const Case &c : cases) {
        const QByteArray deb = QByteArrayLiteral("exit-code-deb-payload");
        FakeServer *server = seedUpdatable(deb);
        QNetworkAccessManager net;
        UpgradeController controller(
            &net, QUrl(server->baseUrl() + "/releases/latest"));
        controller.setSourceValidator(acceptLocalSource);
        QSignalSpy finishedSpy(&controller,
                               &UpgradeController::upgradeFinished);

        controller.setInstallRunner(
            [&](const QString &, const QStringList &,
                std::function<void(int)> onFinished) {
                onFinished(c.exitCode);
            });

        controller.checkForUpdate();
        QTRY_COMPARE(controller.state(), UpgradeController::State::Updatable);
        controller.downloadAndInstall();
        QTRY_COMPARE(controller.state(), c.expected);

        QCOMPARE(finishedSpy.count(), 1);
        QCOMPARE(finishedSpy.at(0).at(0).toBool(), c.exitCode == 0);
        QCOMPARE(finishedSpy.at(0).at(1).toString(),
                 QString::fromUtf8(c.message));
        const UpgradeController::FailedReason expectedReason =
            c.exitCode == 0 ? UpgradeController::FailedReason::None
            : (c.exitCode == 126 || c.exitCode == 127)
            ? UpgradeController::FailedReason::Other
            : UpgradeController::FailedReason::Install;
        QCOMPARE(finishedSpy.at(0).at(2).value<UpgradeController::FailedReason>(),
                 expectedReason);
        QVERIFY(tempDebFiles().isEmpty());

        delete server;
    }
}

void TestUpgradeController::cancelDuringDownload()
{
    const QByteArray body = QByteArrayLiteral("large-deb-body-to-hang");
    FakeServer *server = seedUpdatable(body);
    const QString base = server->baseUrl();
    // 覆盖 /deb 为半包不封尾 → 下载挂起在 Downloading。
    server->addPartial("/deb", body, 5);

    QNetworkAccessManager net;
    UpgradeController controller(&net, QUrl(base + "/releases/latest"));
    controller.setSourceValidator(acceptLocalSource);
    QSignalSpy finishedSpy(&controller, &UpgradeController::upgradeFinished);

    controller.checkForUpdate();
    QTRY_COMPARE(controller.state(), UpgradeController::State::Updatable);
    controller.downloadAndInstall();
    QCOMPARE(controller.state(), UpgradeController::State::Downloading);

    // 等出现下载进度（已写到部分数据、reply 仍未完成）后取消。
    QTRY_VERIFY(controller.state() == UpgradeController::State::Downloading);
    controller.cancel();

    QCOMPARE(controller.state(), UpgradeController::State::Cancelled);
    QCOMPARE(finishedSpy.count(), 1);
    QCOMPARE(finishedSpy.at(0).at(0).toBool(), false);
    QCOMPARE(finishedSpy.at(0).at(1).toString(), QStringLiteral("已取消"));
    QCOMPARE(finishedSpy.at(0).at(2).value<UpgradeController::FailedReason>(),
             UpgradeController::FailedReason::Other);
    QVERIFY(tempDebFiles().isEmpty());
}

void TestUpgradeController::downloadIgnoredWhenNotUpdatable()
{
    // 非 Updatable（初始 Idle）调用 downloadAndInstall 不应启动下载。
    UpgradeController controller;
    controller.downloadAndInstall();
    QCOMPARE(controller.state(), UpgradeController::State::Idle);
}

void TestUpgradeController::downloadFollowsRedirect()
{
    // C1：Qt 5.15 默认 ManualRedirectPolicy 不跟随 302。GitHub browser_download_url
    // 初始指向 github.com，302 → objects.githubusercontent.com；manual 策略下
    // reply 以 302 + 空 body 终止（error==NoError）→ 空文件 commit →
    // verifySha256 永远失败。此处用本地 server 模拟：/deb 返回 302 →
    // /real-deb（真实 body），断言 下载+校验+安装 依然完成。
    const QByteArray deb = QByteArrayLiteral("redirected-deb-payload-0123456789");
    FakeServer *server = new FakeServer(this);
    QVERIFY(server->start());
    const QString base = server->baseUrl();
    server->addJson("/releases/latest", releaseJson(base, "0.1.6"));
    server->addRedirect("/deb", base + "/real-deb");
    server->addRoute("/real-deb", 200, "application/octet-stream", deb);
    server->addRoute("/deb.sha256", 200, "text/plain", shaOf(deb));

    QNetworkAccessManager net;
    UpgradeController controller(&net, QUrl(base + "/releases/latest"));
    controller.setSourceValidator(acceptLocalSource);
    QSignalSpy finishedSpy(&controller, &UpgradeController::upgradeFinished);
    int runnerCalls = 0;
    controller.setInstallRunner(
        [&](const QString &, const QStringList &, std::function<void(int)> onFinished) {
            ++runnerCalls;
            onFinished(0);
        });

    controller.checkForUpdate();
    QTRY_COMPARE(controller.state(), UpgradeController::State::Updatable);
    controller.downloadAndInstall();

    QTRY_COMPARE(controller.state(), UpgradeController::State::Success);
    QCOMPARE(finishedSpy.count(), 1);
    QCOMPARE(finishedSpy.at(0).at(0).toBool(), true);
    QCOMPARE(finishedSpy.at(0).at(2).value<UpgradeController::FailedReason>(),
             UpgradeController::FailedReason::None);
    QCOMPARE(runnerCalls, 1); // 302 被跟随，真实 body 下载校验后进入安装
    QVERIFY(tempDebFiles().isEmpty());
}

void TestUpgradeController::downloadRejectsUntrustedRedirect()
{
    const QByteArray deb = QByteArrayLiteral("redirect-target-deb");
    FakeServer *server = seedUpdatable(deb);
    server->addRedirect(
        "/deb", QStringLiteral("https://evil.example.com/pixiu.deb"));

    QNetworkAccessManager net;
    UpgradeController controller(
        &net, QUrl(server->baseUrl() + "/releases/latest"));
    controller.setSourceValidator(acceptLocalSource);
    QSignalSpy finishedSpy(&controller, &UpgradeController::upgradeFinished);

    controller.checkForUpdate();
    QTRY_COMPARE(controller.state(), UpgradeController::State::Updatable);
    controller.downloadAndInstall();

    QTRY_COMPARE(controller.state(), UpgradeController::State::Failed);
    QCOMPARE(finishedSpy.count(), 1);
    QCOMPARE(finishedSpy.at(0).at(1).toString(),
             QStringLiteral("更新源无效"));
    QCOMPARE(finishedSpy.at(0).at(2).value<UpgradeController::FailedReason>(),
             UpgradeController::FailedReason::InvalidSource);
    QVERIFY(tempDebFiles().isEmpty());
}

void TestUpgradeController::checkTimeoutFails()
{
    // 传输超时：/releases/latest 接受连接后从不响应 → setTransferTimeout(15s)
    // 到时触发 OperationCanceledError → 并入「无法连接更新服务器」失败路径。
    FakeServer server;
    QVERIFY(server.start());
    server.addHang("/releases/latest");

    QNetworkAccessManager net;
    UpgradeController controller(
        &net, QUrl(server.baseUrl() + "/releases/latest"));
    QSignalSpy finishedSpy(&controller, &UpgradeController::upgradeFinished);

    controller.checkForUpdate();
    QTRY_COMPARE_WITH_TIMEOUT(controller.state(),
                              UpgradeController::State::Failed, 20000);
    QCOMPARE(finishedSpy.count(), 1);
    QCOMPARE(finishedSpy.at(0).at(0).toBool(), false);
    QCOMPARE(finishedSpy.at(0).at(1).toString(),
             QStringLiteral("无法连接更新服务器"));
    QCOMPARE(finishedSpy.at(0).at(2).value<UpgradeController::FailedReason>(),
             UpgradeController::FailedReason::Network);
}

void TestUpgradeController::invalidSourceRejected()
{
    // 无效下载源：http:// 协议 或 https:// 非 allowlist host → Failed +
    // 更新源无效，且不发起下载（默认 m_sourceValidator 要求
    // https + GitHub host allowlist；校验在 downloadAndInstall 最前，早于
    // setState(Downloading) 与 get()）。
    struct Case {
        const char *name;
        QByteArray debUrl;
        QByteArray shaUrl;
    };
    const Case cases[] = {
        {"http-scheme", QByteArrayLiteral("http://127.0.0.1:1/deb"),
         QByteArrayLiteral("http://127.0.0.1:1/deb.sha256")},
        {"non-allowlist-host", QByteArrayLiteral("https://evil.example.com/deb"),
         QByteArrayLiteral("https://evil.example.com/deb.sha256")},
    };

    for (const Case &c : cases) {
        FakeServer *server = new FakeServer(this);
        QVERIFY(server->start());
        const QString base = server->baseUrl();
        const QByteArray assetBase =
            "pixiu_0.1.6-1_" + ui::debianArchitecture().toUtf8() + ".deb";
        QByteArray json =
            R"({ "tag_name": "v0.1.6", "assets": [{"name":")" + assetBase
            + R"(","browser_download_url":")" + c.debUrl
            + R"("},{"name":")" + assetBase
            + R"(.sha256","browser_download_url":")" + c.shaUrl
            + R"("} ]})";
        server->addJson("/releases/latest", json);

        QNetworkAccessManager net;
        UpgradeController controller(&net, QUrl(base + "/releases/latest"));
        QList<UpgradeController::State> seen;
        connect(&controller, &UpgradeController::stateChanged, this,
                [&seen](UpgradeController::State s) { seen.append(s); });
        QSignalSpy finishedSpy(&controller, &UpgradeController::upgradeFinished);

        controller.checkForUpdate();
        QTRY_COMPARE(controller.state(), UpgradeController::State::Updatable);
        controller.downloadAndInstall();

        QCOMPARE(controller.state(), UpgradeController::State::Failed);
        QCOMPARE(finishedSpy.count(), 1);
        QCOMPARE(finishedSpy.at(0).at(0).toBool(), false);
        QCOMPARE(finishedSpy.at(0).at(1).toString(),
                 QStringLiteral("更新源无效"));
        QCOMPARE(finishedSpy.at(0).at(2).value<UpgradeController::FailedReason>(),
                 UpgradeController::FailedReason::InvalidSource);
        // 校验在 setState(Downloading) 之前拦截 → 状态机从未进入下载。
        QVERIFY(!seen.contains(UpgradeController::State::Downloading));
        QVERIFY(tempDebFiles().isEmpty());
        delete server;
    }
}

void TestUpgradeController::installProcessStartFailureIsReported()
{
    const QByteArray deb = QByteArrayLiteral("failed-start-deb-payload");
    FakeServer *server = seedUpdatable(deb);
    QNetworkAccessManager net;
    UpgradeController controller(
        &net, QUrl(server->baseUrl() + "/releases/latest"));
    controller.setSourceValidator(acceptLocalSource);
    controller.setInstallProgramForTest(
        QStringLiteral("/definitely/missing/pixiu-pkexec"));
    QSignalSpy finishedSpy(&controller, &UpgradeController::upgradeFinished);

    controller.checkForUpdate();
    QTRY_COMPARE(controller.state(), UpgradeController::State::Updatable);
    controller.downloadAndInstall();

    QTRY_COMPARE(controller.state(), UpgradeController::State::Failed);
    QCOMPARE(finishedSpy.count(), 1);
    QCOMPARE(finishedSpy.at(0).at(1).toString(),
             QStringLiteral("无法启动系统安装程序"));
    QCOMPARE(finishedSpy.at(0).at(2).value<UpgradeController::FailedReason>(),
             UpgradeController::FailedReason::Install);
    QVERIFY(tempDebFiles().isEmpty());
}

void TestUpgradeController::oversizedDownloadIsRejected()
{
    const QByteArray deb = QByteArrayLiteral("declared-oversized-package");
    FakeServer *server = seedUpdatable(deb);
    server->addPartialWithDeclaredLength(
        "/deb", QByteArrayLiteral("x"), 600LL * 1024 * 1024);

    QNetworkAccessManager net;
    UpgradeController controller(
        &net, QUrl(server->baseUrl() + "/releases/latest"));
    controller.setSourceValidator(acceptLocalSource);
    QSignalSpy finishedSpy(&controller, &UpgradeController::upgradeFinished);

    controller.checkForUpdate();
    QTRY_COMPARE(controller.state(), UpgradeController::State::Updatable);
    controller.downloadAndInstall();

    QTRY_COMPARE(controller.state(), UpgradeController::State::Failed);
    QCOMPARE(finishedSpy.count(), 1);
    QCOMPARE(finishedSpy.at(0).at(2).value<UpgradeController::FailedReason>(),
             UpgradeController::FailedReason::Download);
    QVERIFY(tempDebFiles().isEmpty());
}

void TestUpgradeController::oversizedChecksumIsRejected()
{
    const QByteArray deb = QByteArrayLiteral("normal-package");
    FakeServer *server = seedUpdatable(deb);
    server->addRoute(
        "/deb.sha256", 200, "text/plain", QByteArray(70 * 1024, 'a'));

    QNetworkAccessManager net;
    UpgradeController controller(
        &net, QUrl(server->baseUrl() + "/releases/latest"));
    controller.setSourceValidator(acceptLocalSource);
    QSignalSpy finishedSpy(&controller, &UpgradeController::upgradeFinished);

    controller.checkForUpdate();
    QTRY_COMPARE(controller.state(), UpgradeController::State::Updatable);
    controller.downloadAndInstall();

    QTRY_COMPARE(controller.state(), UpgradeController::State::Failed);
    QCOMPARE(finishedSpy.count(), 1);
    QCOMPARE(finishedSpy.at(0).at(2).value<UpgradeController::FailedReason>(),
             UpgradeController::FailedReason::Download);
    QVERIFY(tempDebFiles().isEmpty());
}

QTEST_MAIN(TestUpgradeController)
#include "t_upgrade_controller.moc"
