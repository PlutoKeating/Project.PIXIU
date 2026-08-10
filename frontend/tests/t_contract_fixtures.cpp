#include <QHash>
#include <QHostAddress>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QSignalSpy>
#include <QTcpServer>
#include <QTcpSocket>
#include <QTest>

#include "services/BackendTransport.h"
#include "services/HttpBackendTransport.h"

// 契约一致性测试：以本地 TCP 服务模拟后端，响应形状逐项对齐
// backend/foundation/api/http_app.py 与 backend/foundation/tests/test_api.py
// 的真实实现（2026-08-10 feat/foundation 分支）。
//
// 覆盖：write / query / forget 两段式 / conflicts / preference history /
// sync peers+status / sync pair+revoke / flow promote 的请求-响应契约。
class ContractServer : public QObject
{
public:
    explicit ContractServer(QObject *parent = nullptr)
        : QObject(parent)
        , m_server(new QTcpServer(this))
    {
        if (!m_server->listen(QHostAddress::LocalHost, 0)) {
            qFatal("contract server listen failed");
        }
        connect(m_server, &QTcpServer::newConnection, this, [this]() {
            while (m_server->hasPendingConnections()) {
                QTcpSocket *socket = m_server->nextPendingConnection();
                m_buffers.insert(socket, QByteArray());
                connect(socket, &QTcpSocket::readyRead, this,
                        [this, socket]() { serve(socket); });
                connect(socket, &QTcpSocket::disconnected, this,
                        [this, socket]() {
                            m_buffers.remove(socket);
                            socket->deleteLater();
                        });
            }
        });
    }

    quint16 port() const { return m_server->serverPort(); }

private:
    static QString getPath(const QString &requestLine)
    {
        const QStringList parts = requestLine.split(QLatin1Char(' '));
        return parts.value(1);
    }

    static QJsonObject parseBody(const QByteArray &raw)
    {
        const QJsonDocument doc = QJsonDocument::fromJson(raw);
        return doc.isObject() ? doc.object() : QJsonObject();
    }

    void serve(QTcpSocket *socket)
    {
        QByteArray &buffer = m_buffers[socket];
        buffer += socket->readAll();

        const int headerEnd = buffer.indexOf("\r\n\r\n");
        if (headerEnd < 0) {
            return;
        }
        int contentLength = 0;
        const QByteArray headers = buffer.left(headerEnd);
        const QList<QByteArray> lines = headers.split('\n');
        if (lines.isEmpty()) {
            return;
        }
        for (const QByteArray &line : lines) {
            const QByteArray trimmed = line.trimmed();
            if (trimmed.startsWith("Content-Length:")) {
                contentLength =
                    trimmed.mid(QByteArrayLiteral("Content-Length:").size())
                        .trimmed()
                        .toInt();
            }
        }
        if (buffer.size() < headerEnd + 4 + contentLength) {
            return;
        }

        const QString requestLine =
            QString::fromLatin1(lines.first().trimmed());
        const QString path = getPath(requestLine);
        const QByteArray bodyRaw =
            buffer.mid(headerEnd + 4, contentLength);
        const QJsonObject body = parseBody(bodyRaw);
        buffer.clear();

        const QJsonObject response = route(path, body);
        respond(socket, response);
    }

    QJsonObject route(const QString &path, const QJsonObject &body)
    {
        const QString evd = QStringLiteral("evd_01HAAAAAAAAAAAAAAAAAAAAAA");
        const QString knw = QStringLiteral("knw_02KAAAAAAAAAAAAAAAAAAAAAA");
        const QString cfl = QStringLiteral("cfl_03CAAAAAAAAAAAAAAAAAAAAAA");
        const QString pref = QStringLiteral("pref_04DAAAAAAAAAAAAAAAAAAAAAA");
        const QString selfDev = QStringLiteral("dev_05EAAAAAAAAAAAAAAAAAAAAAA");
        const QString peerDev = QStringLiteral("dev_06FAAAAAAAAAAAAAAAAAAAAAA");

        if (path == QStringLiteral("/memory/write")) {
            return QJsonObject{
                {QStringLiteral("evidence_id"), evd},
                {QStringLiteral("status"), QStringLiteral("accepted")},
                {QStringLiteral("quality_score"), 0.94},
                {QStringLiteral("sensitivity"), 0},
                {QStringLiteral("preference_count"), 1},
                {QStringLiteral("conflict_detected"), false},
                {QStringLiteral("latency_ms"), 42},
            };
        }
        if (path == QStringLiteral("/memory/query")) {
            return QJsonObject{
                {QStringLiteral("answer"),
                 QStringLiteral("2026年4月，你们在水电燃气方面共支出 434.50 元")},
                {QStringLiteral("source_evidence"), QJsonArray{evd}},
                {QStringLiteral("source_knowledge"), knw},
                {QStringLiteral("confidence"), 0.93},
                {QStringLiteral("latency_ms"), 210},
            };
        }
        if (path == QStringLiteral("/forget")) {
            if (body.value(QStringLiteral("confirm")).toBool(false)) {
                return QJsonObject{
                    {QStringLiteral("status"), QStringLiteral("forgotten")},
                    {QStringLiteral("forgotten_ids"), QJsonArray{knw, evd}},
                    {QStringLiteral("latency_ms"), 85},
                };
            }
            return QJsonObject{
                {QStringLiteral("targets"),
                 QJsonArray{QJsonObject{
                     {QStringLiteral("type"), QStringLiteral("knowledge")},
                     {QStringLiteral("id"), knw},
                     {QStringLiteral("title"),
                      QStringLiteral("2026年4月家庭支出清单")}}}},
                {QStringLiteral("cascade"),
                 QJsonObject{{QStringLiteral("evidence_count"), 1},
                             {QStringLiteral("relation_count"), 3}}},
                {QStringLiteral("irreversible"), true},
            };
        }
        if (path == QStringLiteral("/conflicts")) {
            return QJsonObject{
                {QStringLiteral("conflicts"),
                 QJsonArray{QJsonObject{
                     {QStringLiteral("id"), cfl},
                     {QStringLiteral("target_knowledge"), knw},
                     {QStringLiteral("field"),
                      QStringLiteral("body.items[2].amount")},
                     {QStringLiteral("old_value"), 156},
                     {QStringLiteral("new_value"), 186},
                     {QStringLiteral("resolution"), QStringLiteral("NEW_WINS")},
                     {QStringLiteral("created_at"), 1714608000},
                 }}},
            };
        }
        if (path.startsWith(QStringLiteral("/preference/"))
            && path.endsWith(QStringLiteral("/history"))) {
            return QJsonObject{
                {QStringLiteral("id"), pref},
                {QStringLiteral("key"), QStringLiteral("output_style.compact")},
                {QStringLiteral("current_version"), 2},
                {QStringLiteral("history"),
                 QJsonArray{
                     QJsonObject{
                         {QStringLiteral("version"), 1},
                         {QStringLiteral("value"),
                          QJsonObject{{QStringLiteral("enabled"), false}}},
                         {QStringLiteral("updated_at"), 1714435200},
                     },
                     QJsonObject{
                         {QStringLiteral("version"), 2},
                         {QStringLiteral("value"),
                          QJsonObject{{QStringLiteral("enabled"), true}}},
                         {QStringLiteral("updated_at"), 1714521600},
                     },
                 }},
            };
        }
        if (path == QStringLiteral("/sync/peers")) {
            return QJsonObject{
                {QStringLiteral("peers"),
                 QJsonArray{
                     QJsonObject{
                         {QStringLiteral("id"), selfDev},
                         {QStringLiteral("name"), QStringLiteral("书房工作站")},
                         {QStringLiteral("is_self"), true},
                         {QStringLiteral("status"), QStringLiteral("ONLINE")},
                         {QStringLiteral("last_sync_ts"),
                          QJsonValue(QJsonValue::Null)},
                         {QStringLiteral("pending_ops"), 0},
                     },
                     QJsonObject{
                         {QStringLiteral("id"), peerDev},
                         {QStringLiteral("name"), QStringLiteral("客厅一体机")},
                         {QStringLiteral("is_self"), false},
                         {QStringLiteral("status"), QStringLiteral("ONLINE")},
                         {QStringLiteral("last_sync_ts"), 1714607900},
                         {QStringLiteral("pending_ops"), 3},
                     },
                 }},
            };
        }
        if (path == QStringLiteral("/sync/status")) {
            return QJsonObject{
                {QStringLiteral("domain"), QStringLiteral("shared:home")},
                {QStringLiteral("peers_online"), 2},
                {QStringLiteral("peers_total"), 2},
                {QStringLiteral("pending_outgoing_ops"), 0},
                {QStringLiteral("last_anti_entropy_ts"),
                 QJsonValue(QJsonValue::Null)},
                {QStringLiteral("total_ops_synced"), 1285},
            };
        }
        if (path == QStringLiteral("/sync/pair")) {
            return QJsonObject{
                {QStringLiteral("peer_id"), peerDev},
                {QStringLiteral("device_name"), QStringLiteral("客厅一体机")},
                {QStringLiteral("domain"), QStringLiteral("shared:home")},
                {QStringLiteral("status"), QStringLiteral("paired")},
            };
        }
        if (path.startsWith(QStringLiteral("/sync/peers/"))
            && path.endsWith(QStringLiteral("/revoke"))) {
            return QJsonObject{
                {QStringLiteral("status"), QStringLiteral("revoked")},
                {QStringLiteral("peer_id"), peerDev},
                {QStringLiteral("domain"), QStringLiteral("shared:home")},
            };
        }
        if (path == QStringLiteral("/memory/flow/promote")) {
            return QJsonObject{
                {QStringLiteral("promoted_count"), 1},
                {QStringLiteral("knowledge_ids"),
                 QJsonArray{QStringLiteral("knw_03GAAAAAAAAAAAAAAAAAAAAAA")}},
                {QStringLiteral("latency_ms"), 3200},
            };
        }
        return QJsonObject{
            {QStringLiteral("detail"), QStringLiteral("NOT_FOUND")},
        };
    }

    static void respond(QTcpSocket *socket, const QJsonObject &body)
    {
        const QByteArray json =
            QJsonDocument(body).toJson(QJsonDocument::Compact);
        const QByteArray response =
            "HTTP/1.1 200 OK\r\n"
            "Content-Type: application/json\r\n"
            "Content-Length: " +
            QByteArray::number(json.size()) +
            "\r\n"
            "Connection: close\r\n"
            "\r\n" +
            json;
        socket->write(response);
        socket->flush();
        socket->disconnectFromHost();
    }

    QTcpServer *m_server = nullptr;
    QHash<QTcpSocket *, QByteArray> m_buffers;
};

class TestContractFixtures : public QObject
{
    Q_OBJECT

private slots:
    void init();
    void cleanup();

    void writeMatchesBackendContract();
    void queryMatchesBackendContract();
    void forgetTwoStageMatchesBackendContract();
    void conflictsMatchBackendContract();
    void preferenceHistoryMatchesBackendContract();
    void syncPeersAndStatusMatchBackendContract();
    void syncPairAndRevokeMatchBackendContract();
    void flowPromoteMatchesBackendContract();

private:
    HttpBackendTransport *makeTransport();

    ContractServer *m_server = nullptr;
    HttpBackendTransport *m_transport = nullptr;
};

void TestContractFixtures::init()
{
    qRegisterMetaType<ConnectionState>("ConnectionState");
    m_server = new ContractServer(this);
    m_transport = nullptr;
}

void TestContractFixtures::cleanup()
{
    delete m_transport;
    m_transport = nullptr;
    delete m_server;
    m_server = nullptr;
}

HttpBackendTransport *TestContractFixtures::makeTransport()
{
    qputenv("PIXIU_BACKEND_URL",
            QStringLiteral("http://127.0.0.1:%1")
                .arg(m_server->port())
                .toUtf8());
    m_transport = new HttpBackendTransport(this);
    m_transport->connectToBackend();
    return m_transport;
}

void TestContractFixtures::writeMatchesBackendContract()
{
    HttpBackendTransport *transport = makeTransport();
    QSignalSpy spy(transport, &BackendTransport::writeAcknowledged);

    QJsonObject raw;
    raw.insert(QStringLiteral("title"), QStringLiteral("测试"));
    raw.insert(QStringLiteral("body"),
               QJsonObject{{QStringLiteral("text"), QStringLiteral("内容")}});
    QJsonObject payload;
    payload.insert(QStringLiteral("source_type"), QStringLiteral("MANUAL_CONFIG"));
    payload.insert(QStringLiteral("raw"), raw);
    payload.insert(QStringLiteral("scope"), QStringLiteral("user:local"));

    transport->writeMemory(payload);

    QTRY_COMPARE_WITH_TIMEOUT(spy.count(), 1, 3000);
    const QJsonObject response = spy.takeFirst().at(0).toJsonObject();
    QVERIFY(response.value(QStringLiteral("evidence_id")).toString().startsWith(
        QStringLiteral("evd_")));
    QCOMPARE(response.value(QStringLiteral("status")).toString(),
             QStringLiteral("accepted"));
    QVERIFY(response.value(QStringLiteral("quality_score")).toDouble() > 0);
    QCOMPARE(response.value(QStringLiteral("sensitivity")).toInt(), 0);
    QVERIFY(response.contains(QStringLiteral("preference_count")));
    QVERIFY(response.contains(QStringLiteral("conflict_detected")));
    QVERIFY(response.value(QStringLiteral("latency_ms")).toInt() >= 0);
}

void TestContractFixtures::queryMatchesBackendContract()
{
    HttpBackendTransport *transport = makeTransport();
    QSignalSpy spy(transport, &BackendTransport::queryResult);

    QJsonObject hint;
    hint.insert(QStringLiteral("top_k"), 5);
    transport->queryMemory(QStringLiteral("水电燃气花了多少钱"), hint);

    QTRY_COMPARE_WITH_TIMEOUT(spy.count(), 1, 3000);
    const QJsonObject atom = spy.takeFirst().at(1).toJsonObject();
    QVERIFY(!atom.value(QStringLiteral("answer")).toString().isEmpty());
    QCOMPARE(atom.value(QStringLiteral("source_knowledge")).toString(),
             QStringLiteral("knw_02KAAAAAAAAAAAAAAAAAAAAAA"));
    QCOMPARE(atom.value(QStringLiteral("source_evidence")).toArray().size(), 1);
    QVERIFY(atom.value(QStringLiteral("confidence")).toDouble() > 0.0);
    QVERIFY(atom.value(QStringLiteral("latency_ms")).toInt() > 0);
}

void TestContractFixtures::forgetTwoStageMatchesBackendContract()
{
    HttpBackendTransport *transport = makeTransport();
    QSignalSpy spy(transport, &BackendTransport::forgetResult);

    transport->forget(QStringLiteral("忘记那张4月支出清单"), false);
    QTRY_COMPARE_WITH_TIMEOUT(spy.count(), 1, 3000);
    const QJsonObject pending = spy.takeFirst().at(0).toJsonObject();
    QVERIFY(pending.value(QStringLiteral("targets")).toArray().size() >= 1);
    QVERIFY(pending.value(QStringLiteral("cascade")).toObject().contains(
        QStringLiteral("evidence_count")));
    QCOMPARE(pending.value(QStringLiteral("irreversible")).toBool(), true);

    transport->forget(QStringLiteral("忘记那张4月支出清单"), true);
    QTRY_COMPARE_WITH_TIMEOUT(spy.count(), 1, 3000);
    const QJsonObject done = spy.takeFirst().at(0).toJsonObject();
    QCOMPARE(done.value(QStringLiteral("status")).toString(),
             QStringLiteral("forgotten"));
    QCOMPARE(done.value(QStringLiteral("forgotten_ids")).toArray().size(), 2);
}

void TestContractFixtures::conflictsMatchBackendContract()
{
    HttpBackendTransport *transport = makeTransport();
    QSignalSpy spy(transport, &BackendTransport::conflictsResult);

    transport->listConflicts();

    QTRY_COMPARE_WITH_TIMEOUT(spy.count(), 1, 3000);
    const QJsonArray conflicts = spy.takeFirst().at(0).toJsonArray();
    QCOMPARE(conflicts.size(), 1);
    const QJsonObject item = conflicts.first().toObject();
    QVERIFY(item.value(QStringLiteral("id")).toString().startsWith(
        QStringLiteral("cfl_")));
    QCOMPARE(item.value(QStringLiteral("old_value")).toInt(), 156);
    QCOMPARE(item.value(QStringLiteral("new_value")).toInt(), 186);
    QCOMPARE(item.value(QStringLiteral("resolution")).toString(),
             QStringLiteral("NEW_WINS"));
    QVERIFY(item.contains(QStringLiteral("created_at")));
}

void TestContractFixtures::preferenceHistoryMatchesBackendContract()
{
    HttpBackendTransport *transport = makeTransport();
    QSignalSpy spy(transport, &BackendTransport::preferenceHistoryResult);

    transport->preferenceHistory(
        QStringLiteral("pref_04DAAAAAAAAAAAAAAAAAAAAAA"));

    QTRY_COMPARE_WITH_TIMEOUT(spy.count(), 1, 3000);
    const QJsonObject response = spy.takeFirst().at(0).toJsonObject();
    QCOMPARE(response.value(QStringLiteral("key")).toString(),
             QStringLiteral("output_style.compact"));
    QCOMPARE(response.value(QStringLiteral("current_version")).toInt(), 2);
    const QJsonArray history = response.value(QStringLiteral("history")).toArray();
    QCOMPARE(history.size(), 2);
    QCOMPARE(history.first().toObject().value(QStringLiteral("version")).toInt(), 1);
}

void TestContractFixtures::syncPeersAndStatusMatchBackendContract()
{
    HttpBackendTransport *transport = makeTransport();
    QSignalSpy peersSpy(transport, &BackendTransport::peersResult);
    QSignalSpy statusSpy(transport, &BackendTransport::syncStatusResult);

    transport->listPeers();
    transport->syncStatus();

    QTRY_COMPARE_WITH_TIMEOUT(peersSpy.count(), 1, 3000);
    const QJsonObject peersBody = peersSpy.takeFirst().at(0).toJsonObject();
    QVERIFY(peersBody.contains(QStringLiteral("peers")));
    const QJsonArray peers = peersBody.value(QStringLiteral("peers")).toArray();
    QCOMPARE(peers.size(), 2);
    QCOMPARE(peers.first().toObject().value(QStringLiteral("is_self")).toBool(),
             true);
    QCOMPARE(peers.first().toObject().value(QStringLiteral("status")).toString(),
             QStringLiteral("ONLINE"));
    QCOMPARE(peers.at(1).toObject().value(QStringLiteral("pending_ops")).toInt(),
             3);

    QTRY_COMPARE_WITH_TIMEOUT(statusSpy.count(), 1, 3000);
    const QJsonObject status = statusSpy.takeFirst().at(0).toJsonObject();
    QCOMPARE(status.value(QStringLiteral("domain")).toString(),
             QStringLiteral("shared:home"));
    QCOMPARE(status.value(QStringLiteral("peers_online")).toInt(), 2);
    QCOMPARE(status.value(QStringLiteral("peers_total")).toInt(), 2);
    QCOMPARE(status.value(QStringLiteral("pending_outgoing_ops")).toInt(), 0);
    QCOMPARE(status.value(QStringLiteral("total_ops_synced")).toInt(), 1285);
    QVERIFY(status.contains(QStringLiteral("last_anti_entropy_ts")));
}

void TestContractFixtures::syncPairAndRevokeMatchBackendContract()
{
    HttpBackendTransport *transport = makeTransport();
    QSignalSpy pairSpy(transport, &BackendTransport::pairResult);
    QSignalSpy revokeSpy(transport, &BackendTransport::revokeResult);

    QJsonObject pairPayload;
    pairPayload.insert(QStringLiteral("method"), QStringLiteral("PIN"));
    pairPayload.insert(QStringLiteral("pin"), QStringLiteral("123456"));
    pairPayload.insert(QStringLiteral("token"), QStringLiteral("remote-token"));
    transport->pairDevice(pairPayload);

    QTRY_COMPARE_WITH_TIMEOUT(pairSpy.count(), 1, 3000);
    const QJsonObject pair = pairSpy.takeFirst().at(0).toJsonObject();
    QCOMPARE(pair.value(QStringLiteral("status")).toString(),
             QStringLiteral("paired"));
    QVERIFY(pair.value(QStringLiteral("peer_id")).toString().startsWith(
        QStringLiteral("dev_")));
    QCOMPARE(pair.value(QStringLiteral("domain")).toString(),
             QStringLiteral("shared:home"));

    transport->revokePeer(QStringLiteral("dev_06FAAAAAAAAAAAAAAAAAAAAAA"));
    QTRY_COMPARE_WITH_TIMEOUT(revokeSpy.count(), 1, 3000);
    const QJsonObject revoke = revokeSpy.takeFirst().at(0).toJsonObject();
    QCOMPARE(revoke.value(QStringLiteral("status")).toString(),
             QStringLiteral("revoked"));
    QCOMPARE(revoke.value(QStringLiteral("peer_id")).toString(),
             QStringLiteral("dev_06FAAAAAAAAAAAAAAAAAAAAAA"));
}

void TestContractFixtures::flowPromoteMatchesBackendContract()
{
    HttpBackendTransport *transport = makeTransport();
    QSignalSpy spy(transport, &BackendTransport::promoteResult);

    QJsonObject payload;
    payload.insert(QStringLiteral("source"), QStringLiteral("SHORT_TERM"));
    payload.insert(
        QStringLiteral("context_ids"),
        QJsonArray{QStringLiteral("ctx_AAAAAAAAAAAAAAAAAAAAAAAAAA")});
    payload.insert(QStringLiteral("scope"), QStringLiteral("user:alice"));
    transport->promoteMemory(payload);

    QTRY_COMPARE_WITH_TIMEOUT(spy.count(), 1, 3000);
    const QJsonObject response = spy.takeFirst().at(0).toJsonObject();
    QCOMPARE(response.value(QStringLiteral("promoted_count")).toInt(), 1);
    QVERIFY(response.value(QStringLiteral("knowledge_ids")).toArray().size() == 1);
    QVERIFY(response.value(QStringLiteral("latency_ms")).toInt() >= 0);
}

QTEST_MAIN(TestContractFixtures)
#include "t_contract_fixtures.moc"
