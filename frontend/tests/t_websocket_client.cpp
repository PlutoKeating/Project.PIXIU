#include <QHostAddress>
#include <QJsonDocument>
#include <QJsonObject>
#include <QSignalSpy>
#include <QTest>
#include <QWebSocket>
#include <QWebSocketServer>

#include "services/WebSocketClient.h"

// WebSocketClient 契约测试：以本地 QWebSocketServer 模拟后端 /events。
//
// 覆盖：HTTP 基址到 ws://…/events 的映射、控制事件不抛业务事件、
// memory_ready 正常上抛、未知事件/畸形帧安全忽略。
class TestWebSocketClient : public QObject
{
    Q_OBJECT

private slots:
    void init();
    void cleanup();

    void httpUrlMapsToWsEvents();
    void controlEventsAreNotForwarded();
    void memoryReadyIsForwarded();
    void unknownEventIsIgnored();
    void malformedFrameIsIgnored();

private:
    void connectClientAndWaitServer();
    void sendFrame(const QByteArray &frame);

    QWebSocketServer *m_server = nullptr;
    QWebSocket *m_serverSocket = nullptr;
    WebSocketClient *m_client = nullptr;
};

void TestWebSocketClient::init()
{
    m_server = new QWebSocketServer(QStringLiteral("pixiu-test"),
                                    QWebSocketServer::NonSecureMode, this);
    QVERIFY(m_server->listen(QHostAddress::LocalHost, 0));
    connect(m_server, &QWebSocketServer::newConnection, this, [this]() {
        m_serverSocket = m_server->nextPendingConnection();
    });

    m_client = new WebSocketClient(this);
    m_client->setBackendUrl(
        QStringLiteral("http://127.0.0.1:%1").arg(m_server->serverPort()));
}

void TestWebSocketClient::cleanup()
{
    if (m_client) {
        m_client->disconnectFromBackend();
        delete m_client;
    }
    m_client = nullptr;
    m_serverSocket = nullptr;
    delete m_server;
    m_server = nullptr;
}

void TestWebSocketClient::connectClientAndWaitServer()
{
    m_client->connectToBackend();
    QTRY_VERIFY_WITH_TIMEOUT(m_serverSocket != nullptr, 3000);
    QTRY_VERIFY_WITH_TIMEOUT(m_client->isConnected(), 3000);
}

void TestWebSocketClient::sendFrame(const QByteArray &frame)
{
    QVERIFY(m_serverSocket != nullptr);
    QVERIFY(m_serverSocket->isValid());
    m_serverSocket->sendTextMessage(QString::fromUtf8(frame));
}

void TestWebSocketClient::httpUrlMapsToWsEvents()
{
    connectClientAndWaitServer();

    QCOMPARE(m_serverSocket->requestUrl().scheme(), QStringLiteral("ws"));
    QCOMPARE(m_serverSocket->requestUrl().path(), QStringLiteral("/events"));
}

void TestWebSocketClient::controlEventsAreNotForwarded()
{
    QSignalSpy spy(m_client, &WebSocketClient::eventReceived);
    connectClientAndWaitServer();

    sendFrame("{\"event\":\"connected\",\"data\":{}}");
    sendFrame("{\"event\":\"ping\",\"data\":{}}");
    QTest::qWait(200);
    QCOMPARE(spy.count(), 0);
}

void TestWebSocketClient::memoryReadyIsForwarded()
{
    QSignalSpy spy(m_client, &WebSocketClient::eventReceived);
    connectClientAndWaitServer();

    sendFrame("{\"event\":\"memory_ready\",\"data\":{"
              "\"evidence_id\":\"evd_1\",\"knowledge_id\":\"knw_1\","
              "\"title\":\"测试记忆\",\"scope\":\"user:alice\"}}");
    QTRY_COMPARE_WITH_TIMEOUT(spy.count(), 1, 3000);

    const QJsonObject event = spy.takeFirst().at(0).toJsonObject();
    QCOMPARE(event.value(QStringLiteral("event")).toString(),
             QStringLiteral("memory_ready"));
    const QJsonObject data = event.value(QStringLiteral("data")).toObject();
    QCOMPARE(data.value(QStringLiteral("knowledge_id")).toString(),
             QStringLiteral("knw_1"));
    QCOMPARE(data.value(QStringLiteral("title")).toString(),
             QStringLiteral("测试记忆"));
}

void TestWebSocketClient::unknownEventIsIgnored()
{
    QSignalSpy spy(m_client, &WebSocketClient::eventReceived);
    connectClientAndWaitServer();

    sendFrame("{\"event\":\"some_future_event\",\"data\":{\"x\":1}}");
    QTest::qWait(200);
    QCOMPARE(spy.count(), 0);
}

void TestWebSocketClient::malformedFrameIsIgnored()
{
    QSignalSpy spy(m_client, &WebSocketClient::eventReceived);
    connectClientAndWaitServer();

    sendFrame("this is not json");
    QTest::qWait(200);
    QCOMPARE(spy.count(), 0);
}

QTEST_MAIN(TestWebSocketClient)
#include "t_websocket_client.moc"
