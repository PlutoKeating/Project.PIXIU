#include <QHostAddress>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QSignalSpy>
#include <QTcpServer>
#include <QTcpSocket>
#include <QTest>
#include <QTimer>

#include "services/BackendTypes.h"
#include "services/BackendTransport.h"
#include "services/HttpBackendTransport.h"

// HttpBackendTransport 契约测试：以本地 QTcpServer 模拟后端。
//
// 覆盖：初始健康探测置 Connected、周期探测在“后端中途挂掉→恢复”时自动
// 刷新连接状态（无需用户请求）、健康探测静默（不广播 conflictsResult /
// errorOccurred，避免干扰冲突/写入/配对等控制器）。
class TestHttpBackend : public QObject
{
    Q_OBJECT

private slots:
    void init();
    void cleanup();

    void connectsWhenBackendUp();
    void detectsDropAndRecovery();
    void probesAreSilentForControllers();
    void mapsFastApiDetailErrors();
    void mapsFastApiValidationErrors();
    void keepsLegacyErrorShape();
    void rejectsUnreadyHealth_data();
    void rejectsUnreadyHealth();
    void disconnectRejectsPendingReplies();
    void startsHealthAfterBusinessReachability();
    void diagnosticsStopOnFailedRead();
    void diagnosticsReadAllPublicEndpoints();
    void digestPreservesSelectedDate();

private:
    HttpBackendTransport *makeTransport(int intervalMs = 300);
    void startServer(quint16 port = 0);
    void stopServer();

    QTcpServer *m_server = nullptr;
    HttpBackendTransport *m_transport = nullptr;
    QByteArray m_healthBody;
    int m_replyDelay = 0;
    int m_requests = 0;
    QList<QByteArray> m_paths;
    bool m_serveMetadata = false;
};

void TestHttpBackend::init()
{
    qRegisterMetaType<ConnectionState>("ConnectionState");
    m_transport = nullptr;
    m_server = nullptr;
    m_healthBody = R"({"status":"ready","component":"pixiu-memory-backend","database":"ok"})";
    m_replyDelay = 0;
    m_requests = 0;
    m_paths.clear();
    m_serveMetadata = false;
}

void TestHttpBackend::cleanup()
{
    delete m_transport;
    m_transport = nullptr;
    stopServer();
}

void TestHttpBackend::startServer(quint16 port)
{
    m_server = new QTcpServer(this);
    QVERIFY(m_server->listen(QHostAddress::LocalHost, port));
    connect(m_server, &QTcpServer::newConnection, this, [this]() {
        while (m_server->hasPendingConnections()) {
            QTcpSocket *socket = m_server->nextPendingConnection();
            connect(socket, &QTcpSocket::readyRead, this, [this, socket]() {
                if (socket->property("handled").toBool()) {
                    socket->readAll();
                    return;
                }
                if (!socket->canReadLine()) {
                    return;
                }
                const QByteArray requestLine = socket->readLine().trimmed();
                socket->setProperty("handled", true);
                socket->readAll();
                const QList<QByteArray> parts = requestLine.split(' ');
                const QByteArray method =
                    parts.value(0).toUpper();
                const QByteArray path = parts.value(1);
                ++m_requests;
                m_paths.append(path);

                // 按请求路径返回不同响应，覆盖后端真实错误形状与旧契约形状。
                QJsonObject body;
                int status = 200;
                if (method == "GET" && path == "/health") {
                    body = QJsonDocument::fromJson(m_healthBody).object();
                } else if (method == "GET" && path == "/version" && m_serveMetadata) {
                    body = {{"component", "pixiu-memory-backend"}, {"product_version", "9.9.9"},
                            {"api_version", "0.5.0"}, {"agent_memory_api", 1}, {"schema_version", 12}};
                } else if (method == "GET" && path == "/capabilities" && m_serveMetadata) {
                    body = {{"contest_ready", false}, {"embedding", QJsonObject{{"runtime", "portable"}}}};
                } else if (method == "GET" && path == "/conflicts") {
                    body = QJsonObject{
                        {QStringLiteral("conflicts"), QJsonArray()}};
                } else if (method == "POST" && path == "/forget") {
                    status = 404;
                    body = QJsonObject{
                        {QStringLiteral("detail"),
                         QStringLiteral("NOT_FOUND")}};
                } else if (method == "POST" && path == "/memory/query") {
                    status = 422;
                    body = QJsonObject{
                        {QStringLiteral("detail"),
                         QJsonArray{QJsonObject{
                             {QStringLiteral("loc"),
                              QJsonArray{QStringLiteral("body"),
                                         QStringLiteral("text")}},
                             {QStringLiteral("msg"),
                              QStringLiteral(
                                  "String should have at least 1 character")},
                             {QStringLiteral("type"),
                              QStringLiteral("string_too_short")}}}}};
                } else if (method == "POST" && path == "/memory/write") {
                    status = 500;
                    body = QJsonObject{
                        {QStringLiteral("error"),
                         QStringLiteral("INTERNAL_ERROR")},
                        {QStringLiteral("message"),
                         QStringLiteral("boom")},
                        {QStringLiteral("request_id"),
                         QStringLiteral("req_x")}};
                } else {
                    status = 404;
                    body = QJsonObject{
                        {QStringLiteral("detail"),
                         QStringLiteral("NOT_FOUND")}};
                }

                const QByteArray json = path == "/health" ? m_healthBody
                    : QJsonDocument(body).toJson(QJsonDocument::Compact);
                const QByteArray response =
                    "HTTP/1.1 " +
                    QByteArray::number(status) +
                    " X\r\n"
                    "Content-Type: application/json\r\n"
                    "Content-Length: " +
                    QByteArray::number(json.size()) +
                    "\r\n"
                    "Connection: close\r\n"
                    "\r\n" +
                    json;
                QTimer::singleShot(m_replyDelay, socket, [socket, response]() {
                    socket->write(response);
                    socket->flush();
                    socket->disconnectFromHost();
                });
            });
            connect(socket, &QTcpSocket::disconnected,
                    socket, &QTcpSocket::deleteLater);
        }
    });
}

void TestHttpBackend::stopServer()
{
    if (m_server) {
        m_server->close();
        delete m_server;
        m_server = nullptr;
    }
}

HttpBackendTransport *TestHttpBackend::makeTransport(int intervalMs)
{
    if (!m_server) {
        qFatal("HTTP backend test: server not started");
    }
    qputenv("PIXIU_BACKEND_URL",
            QStringLiteral("http://127.0.0.1:%1")
                .arg(m_server->serverPort())
                .toUtf8());
    m_transport = new HttpBackendTransport(nullptr, intervalMs);
    return m_transport;
}

void TestHttpBackend::connectsWhenBackendUp()
{
    startServer();
    HttpBackendTransport *transport = makeTransport();
    transport->connectToBackend();
    QTRY_VERIFY_WITH_TIMEOUT(
        transport->connectionState() == ConnectionState::Connected, 3000);
}

void TestHttpBackend::detectsDropAndRecovery()
{
    startServer();
    HttpBackendTransport *transport = makeTransport(300);
    transport->connectToBackend();
    QTRY_VERIFY_WITH_TIMEOUT(
        transport->connectionState() == ConnectionState::Connected, 3000);

    // 后端中途挂掉：无需任何用户请求，周期探测应在数个间隔内转为 Error。
    const quint16 port = m_server->serverPort();
    stopServer();
    QTRY_VERIFY_WITH_TIMEOUT(
        transport->connectionState() == ConnectionState::Error, 3000);

    // 后端恢复：周期探测自动转回 Connected（顶栏状态无需等下一次用户操作）。
    startServer(port);
    QTRY_VERIFY_WITH_TIMEOUT(
        transport->connectionState() == ConnectionState::Connected, 3000);
}

void TestHttpBackend::probesAreSilentForControllers()
{
    startServer();
    HttpBackendTransport *transport = makeTransport(200);
    QSignalSpy conflictsSpy(transport, &BackendTransport::conflictsResult);
    QSignalSpy errorSpy(transport, &BackendTransport::errorOccurred);

    transport->connectToBackend();
    QTRY_VERIFY_WITH_TIMEOUT(
        transport->connectionState() == ConnectionState::Connected, 3000);
    // 多轮周期探测（在线 + 离线）均不应广播业务信号。
    QTest::qWait(700);
    stopServer();
    QTRY_VERIFY_WITH_TIMEOUT(
        transport->connectionState() == ConnectionState::Error, 3000);
    QTest::qWait(700);

    QCOMPARE(conflictsSpy.count(), 0);
    QCOMPARE(errorSpy.count(), 0);
}

void TestHttpBackend::mapsFastApiDetailErrors()
{
    startServer();
    HttpBackendTransport *transport = makeTransport();
    QSignalSpy errorSpy(transport, &BackendTransport::errorOccurred);

    transport->forget(QStringLiteral("x"), false);

    QTRY_COMPARE_WITH_TIMEOUT(errorSpy.count(), 1, 3000);
    const QList<QVariant> args = errorSpy.takeFirst();
    QCOMPARE(args.at(0).toString(), QStringLiteral("NOT_FOUND"));
    QCOMPARE(args.at(1).toString(), QStringLiteral("NOT_FOUND"));
}

void TestHttpBackend::mapsFastApiValidationErrors()
{
    startServer();
    HttpBackendTransport *transport = makeTransport();
    QSignalSpy failedSpy(transport, &BackendTransport::queryFailed);

    transport->queryMemory(QStringLiteral(""), QJsonObject());

    QTRY_COMPARE_WITH_TIMEOUT(failedSpy.count(), 1, 3000);
    const QList<QVariant> args = failedSpy.takeFirst();
    QCOMPARE(args.at(1).toString(), QStringLiteral("INVALID_REQUEST"));
    QVERIFY(args.at(2).toString().contains(
        QStringLiteral("at least 1 character")));
}

void TestHttpBackend::keepsLegacyErrorShape()
{
    startServer();
    HttpBackendTransport *transport = makeTransport();
    QSignalSpy errorSpy(transport, &BackendTransport::errorOccurred);

    transport->writeMemory(QJsonObject());

    QTRY_COMPARE_WITH_TIMEOUT(errorSpy.count(), 1, 3000);
    const QList<QVariant> args = errorSpy.takeFirst();
    QCOMPARE(args.at(0).toString(), QStringLiteral("INTERNAL_ERROR"));
    QCOMPARE(args.at(1).toString(), QStringLiteral("boom"));
    QCOMPARE(args.at(2).toString(), QStringLiteral("req_x"));
}

void TestHttpBackend::rejectsUnreadyHealth_data()
{
    QTest::addColumn<QByteArray>("body");
    QTest::newRow("invalid-json") << QByteArray("not json");
    QTest::newRow("wrong-service") << QByteArray(R"({"status":"ready","component":"other","database":"ok"})");
    QTest::newRow("not-ready") << QByteArray(R"({"status":"starting","component":"pixiu-memory-backend","database":"ok"})");
    QTest::newRow("bad-database") << QByteArray(R"({"status":"ready","component":"pixiu-memory-backend","database":"error"})");
    QTest::newRow("missing-fields") << QByteArray("{}");
}

void TestHttpBackend::rejectsUnreadyHealth()
{
    QFETCH(QByteArray, body);
    startServer();
    m_healthBody = body;
    auto *transport = makeTransport(10000);
    QSignalSpy errors(transport, &BackendTransport::errorOccurred);
    transport->connectToBackend();
    QTRY_COMPARE_WITH_TIMEOUT(transport->connectionState(), ConnectionState::Error, 3000);
    QCOMPARE(errors.count(), 0);
    transport->writeMemory({}); // A reachable HTTP 500 is not a ready backend.
    QTRY_COMPARE_WITH_TIMEOUT(errors.count(), 1, 3000);
    QCOMPARE(transport->connectionState(), ConnectionState::Error);
}

void TestHttpBackend::disconnectRejectsPendingReplies()
{
    startServer();
    m_replyDelay = 200;
    auto *transport = makeTransport(10000);
    QSignalSpy errors(transport, &BackendTransport::errorOccurred);
    transport->connectToBackend();
    transport->forget("test", false);
    QTRY_COMPARE_WITH_TIMEOUT(m_requests, 2, 3000);
    transport->disconnectFromBackend();
    QTRY_COMPARE_WITH_TIMEOUT(errors.count(), 1, 3000);
    QTest::qWait(300);
    QCOMPARE(transport->connectionState(), ConnectionState::Disconnected);
    m_replyDelay = 0;
    transport->connectToBackend();
    QTRY_COMPARE_WITH_TIMEOUT(transport->connectionState(), ConnectionState::Connected, 3000);
}

void TestHttpBackend::startsHealthAfterBusinessReachability()
{
    startServer();
    m_healthBody = "{}";
    auto *transport = makeTransport(10000);
    QSignalSpy errors(transport, &BackendTransport::errorOccurred);
    transport->forget("test", false);
    QTRY_COMPARE_WITH_TIMEOUT(errors.count(), 1, 3000);
    QCOMPARE(transport->connectionState(), ConnectionState::Connected);
    transport->connectToBackend();
    QTRY_COMPARE_WITH_TIMEOUT(transport->connectionState(), ConnectionState::Error, 3000);
}

void TestHttpBackend::diagnosticsStopOnFailedRead()
{
    startServer();
    auto *transport = makeTransport();
    QSignalSpy results(transport, &BackendTransport::diagnosticsResult);
    QSignalSpy errors(transport, &BackendTransport::errorOccurred);
    transport->backendDiagnostics();
    QTRY_COMPARE_WITH_TIMEOUT(errors.count(), 1, 3000);
    QCOMPARE(results.count(), 0);
    QCOMPARE(m_paths, QList<QByteArray>({"/health", "/version"}));
}

void TestHttpBackend::digestPreservesSelectedDate()
{
    startServer();
    auto *transport = makeTransport();
    QSignalSpy errors(transport, &BackendTransport::errorOccurred);
    // The fixture returns 404; inspect the actual request target, not a mock call.
    transport->deliveryDigest(QStringLiteral("2024-02-29"));
    QTRY_COMPARE_WITH_TIMEOUT(errors.count(), 1, 3000);
    transport->deliveryDigest();
    QTRY_COMPARE_WITH_TIMEOUT(errors.count(), 2, 3000);
    transport->deliveryDigest(QStringLiteral("2024-02-29&extra=1"));
    QTRY_COMPARE_WITH_TIMEOUT(errors.count(), 3, 3000);
    QCOMPARE(m_paths, QList<QByteArray>({"/delivery/digest?date=2024-02-29",
        "/delivery/digest", "/delivery/digest?date=2024-02-29%26extra%3D1"}));
}

void TestHttpBackend::diagnosticsReadAllPublicEndpoints()
{
    startServer();
    m_serveMetadata = true;
    auto *transport = makeTransport();
    QSignalSpy results(transport, &BackendTransport::diagnosticsResult);
    QSignalSpy errors(transport, &BackendTransport::errorOccurred);
    transport->backendDiagnostics();
    QTRY_COMPARE_WITH_TIMEOUT(results.count(), 1, 3000);
    QCOMPARE(errors.count(), 0);
    QCOMPARE(m_paths, QList<QByteArray>({"/health", "/version", "/capabilities"}));
    const auto report = results.takeFirst().at(0).toJsonObject();
    QCOMPARE(report.value("health").toObject(), QJsonDocument::fromJson(m_healthBody).object());
    QCOMPARE(report.value("version").toObject().value("api_version").toString(), QStringLiteral("0.5.0"));
    QCOMPARE(report.value("capabilities").toObject().value("embedding").toObject().value("runtime").toString(), QStringLiteral("portable"));
}

QTEST_MAIN(TestHttpBackend)
#include "t_http_backend.moc"
