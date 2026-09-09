#include "AgentEvidence.h"
#include "AgentEvidenceClient.h"
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QTest>
#include <QTcpServer>
#include <QTcpSocket>
#include <QSignalSpy>

class AgentEvidenceTest : public QObject {
    Q_OBJECT
    QJsonObject result() const {
        return {{"session_id", "session-1"}, {"turn_id", "turn-1"},
            {"items", QJsonArray{QJsonObject{{"knowledge_id", "knw_example01"},
                {"title", "A remembered fact"}, {"scope", "user:local"},
                {"evidence_ids", QJsonArray{"evd_example01"}}}}}};
    }
    QJsonObject event(const QString &type, const QJsonValue &value = {}) const {
        return {{"event", type}, {"data", QJsonObject{{"name", "pixiu_memory_search"},
            {"tool_call_id", "call-1"}, {"result", value}}}};
    }
    QByteArray response(const QJsonArray &events, const QString &session = "session-1") const {
        QString content;
        for (const auto &entry : events)
            content += QString::fromUtf8(QJsonDocument(entry.toObject()).toJson(QJsonDocument::Compact)) + '\n';
        return QJsonDocument(QJsonObject{{"session_id", session}, {"content", content}}).toJson();
    }
private slots:
    void parsesAutomaticMemorySources() {
        const QJsonObject data{{"session_id", "session-1"}, {"read_scopes", QJsonArray{"user:local"}},
            {"references", QJsonArray{QJsonObject{{"knowledge_id", "knw_example01"},
                {"evidence_id", "evd_example01"}, {"scope", "user:local"},
                {"title", "Remembered fact"}, {"turn_id", "turn-1"}, {"trace_id", "ctx_example01"}}}}};
        const auto result = pixiu::parseMemorySources(QJsonDocument(data).toJson(), "session-1", "user:local");
        QCOMPARE(result.status, pixiu::AgentEvidenceResult::Ready);
        QCOMPARE(result.references.size(), 1);
        QCOMPARE(result.references.first().evidenceId, QString("evd_example01"));
        QCOMPARE(pixiu::parseMemorySources(QJsonDocument(data).toJson(), "another", "user:local").status,
                 pixiu::AgentEvidenceResult::Invalid);
    }
    void rejectsInvalidRequestBeforeNetworking_data() {
        QTest::addColumn<QString>("url");
        QTest::addColumn<QString>("session");
        QTest::addColumn<QString>("scope");
        QTest::newRow("credentials-in-url") << "http://secret:password@localhost" << "session-1" << "user:local";
        QTest::newRow("query") << "http://localhost?token=secret" << "session-1" << "user:local";
        QTest::newRow("fragment") << "http://localhost#fragment" << "session-1" << "user:local";
        QTest::newRow("file") << "file:///etc/passwd" << "session-1" << "user:local";
        QTest::newRow("session-path") << "http://localhost" << "../private" << "user:local";
        QTest::newRow("scope") << "http://localhost" << "session-1" << "all";
    }
    void rejectsInvalidRequestBeforeNetworking() {
        QFETCH(QString, url);
        QFETCH(QString, session);
        QFETCH(QString, scope);
        pixiu::AgentEvidenceClient client;
        QSignalSpy errors(&client, &pixiu::AgentEvidenceClient::failed);
        client.load(QNetworkRequest(QUrl(url)), session, scope);
        QCOMPARE(errors.count(), 1);
        QVERIFY(!client.busy());
        QVERIFY(!errors[0][1].toString().contains("secret"));
        QVERIFY(!errors[0][1].toString().contains("password"));
    }
    void refusesRedirectAndHttpFailure_data() {
        QTest::addColumn<int>("status");
        QTest::newRow("redirect") << 302;
        QTest::newRow("unauthorized") << 401;
    }
    void refusesRedirectAndHttpFailure() {
        QFETCH(int, status);
        QTcpServer server;
        QVERIFY(server.listen(QHostAddress::LocalHost));
        int requests = 0;
        connect(&server, &QTcpServer::newConnection, this, [&] {
            ++requests;
            auto *socket = server.nextPendingConnection();
            connect(socket, &QTcpSocket::readyRead, socket, [=] {
                socket->readAll();
                socket->write("HTTP/1.1 " + QByteArray::number(status) + " Rejected\r\nLocation: /elsewhere\r\nContent-Length: 0\r\nConnection: close\r\n\r\n");
                socket->disconnectFromHost();
            });
        });
        pixiu::AgentEvidenceClient client;
        QSignalSpy errors(&client, &pixiu::AgentEvidenceClient::failed);
        client.load(QNetworkRequest(QUrl(QString("http://127.0.0.1:%1").arg(server.serverPort()))), "session-1", "user:local");
        QTRY_COMPARE(errors.count(), 1);
        QCOMPARE(requests, 1);
        QVERIFY(!client.busy());
    }
    void asyncFetchAndSessionReplacement() {
        QTcpServer server;
        QVERIFY(server.listen(QHostAddress::LocalHost));
        QStringList paths;
        connect(&server, &QTcpServer::newConnection, this, [&] {
            auto *socket = server.nextPendingConnection();
            connect(socket, &QTcpSocket::readyRead, socket, [&, socket] {
                if (!socket->canReadLine()) return;
                paths << QString::fromUtf8(socket->readLine().split(' ').value(1));
                socket->readAll();
                if (paths.last().contains("session-1")) return; // old request hangs
                const auto body = response({}, "session-2");
                socket->write("HTTP/1.1 200 OK\r\nContent-Length: " + QByteArray::number(body.size()) + "\r\nConnection: close\r\n\r\n" + body);
                socket->disconnectFromHost();
            });
        });
        pixiu::AgentEvidenceClient client;
        QSignalSpy errors(&client, &pixiu::AgentEvidenceClient::failed);
        QStringList loaded;
        connect(&client, &pixiu::AgentEvidenceClient::loaded, this, [&](const QString &session, const pixiu::AgentEvidenceResult &r) {
            QCOMPARE(r.status, pixiu::AgentEvidenceResult::Ready);
            loaded << session;
        });
        const QNetworkRequest request(QUrl(QString("http://127.0.0.1:%1").arg(server.serverPort())));
        client.load(request, "session-1", "user:local");
        QTRY_COMPARE(paths.size(), 1);
        client.load(request, "session-2", "user:local");
        QTRY_COMPARE(loaded, QStringList{"session-2"});
        QCOMPARE(paths.last(), QString("/api/sessions/session-2/details"));
        QCOMPARE(errors.count(), 0);
        QVERIFY(!client.busy());
    }
    void timeoutAndCancellation() {
        QTcpServer server;
        QVERIFY(server.listen(QHostAddress::LocalHost));
        pixiu::AgentEvidenceClient client(nullptr, 30);
        QSignalSpy errors(&client, &pixiu::AgentEvidenceClient::failed);
        const QNetworkRequest request(QUrl(QString("http://127.0.0.1:%1").arg(server.serverPort())));
        client.load(request, "session-1", "user:local");
        QTRY_COMPARE(errors.count(), 1);
        QVERIFY(!client.busy());
        client.load(request, "session-1", "user:local");
        client.cancel();
        QTest::qWait(60);
        QCOMPARE(errors.count(), 1);
    }
    void rejectsLargeResponse_data() {
        QTest::addColumn<bool>("declared");
        QTest::newRow("content-length") << true;
        QTest::newRow("streamed-without-length") << false;
    }
    void rejectsLargeResponse() {
        QFETCH(bool, declared);
        QTcpServer server;
        QVERIFY(server.listen(QHostAddress::LocalHost));
        connect(&server, &QTcpServer::newConnection, this, [&] {
            auto *socket = server.nextPendingConnection();
            connect(socket, &QTcpSocket::readyRead, socket, [=] {
                socket->readAll();
                socket->write("HTTP/1.1 200 OK\r\nConnection: close\r\n");
                if (declared) socket->write("Content-Length: 2097153\r\n");
                socket->write("\r\n");
                if (!declared) socket->write(QByteArray(2*1024*1024+1, 'x'));
                socket->disconnectFromHost();
            });
        });
        pixiu::AgentEvidenceClient client;
        QSignalSpy errors(&client, &pixiu::AgentEvidenceClient::failed);
        client.load(QNetworkRequest(QUrl(QString("http://127.0.0.1:%1").arg(server.serverPort()))), "session-1", "user:local");
        QTRY_COMPARE(errors.count(), 1);
        QVERIFY(errors[0][1].toString().contains(QStringLiteral("过大")));
        QVERIFY(!client.busy());
    }
    void verifiedToolResult() {
        auto completed = event("gateway.tool.completed",
            QString::fromUtf8(QJsonDocument(result()).toJson(QJsonDocument::Compact)));
        const auto parsed = pixiu::parseAgentEvidence(response({event("gateway.tool.started"), completed}), "session-1", "user:local");
        QCOMPARE(parsed.status, pixiu::AgentEvidenceResult::Ready);
        QCOMPARE(parsed.references.size(), 1);
        QCOMPARE(parsed.references[0].evidenceId, QString("evd_example01"));
        QCOMPARE(parsed.references[0].title, QString("A remembered fact"));
        QCOMPARE(parsed.references[0].callId, QString("call-1"));
    }
    void rejectsUncorrelatedAndWrongScope() {
        auto completed = event("gateway.tool.completed", result());
        QCOMPARE(pixiu::parseAgentEvidence(response({completed}), "session-1", "user:local").references.size(), 0);
        QCOMPARE(pixiu::parseAgentEvidence(response({event("gateway.tool.started"), completed}), "session-1", "shared:home").references.size(), 0);
        QCOMPARE(pixiu::parseAgentEvidence(response({completed}, "other"), "session-1", "user:local").status, pixiu::AgentEvidenceResult::Invalid);
    }
    void ignoresModelTextAndDuplicateCompletion() {
        auto completed = event("gateway.tool.completed", result());
        const auto parsed = pixiu::parseAgentEvidence(response({QJsonObject{{"event", "agent.completed"},
            {"text", "evd_fake00001"}}, event("gateway.tool.started"), completed, completed}), "session-1", "user:local");
        QCOMPARE(parsed.references.size(), 1);
    }
    void rejectsMalformedAndOversized() {
        QCOMPARE(pixiu::parseAgentEvidence("{}", "session-1", "user:local").status, pixiu::AgentEvidenceResult::Invalid);
        QCOMPARE(pixiu::parseAgentEvidence(QByteArray(2*1024*1024+1, 'x'), "session-1", "user:local").status, pixiu::AgentEvidenceResult::TooLarge);
    }
    void rejectsCrossSessionResultAndMalformedId() {
        auto other = result();
        other["session_id"] = "other";
        QCOMPARE(pixiu::parseAgentEvidence(response({event("gateway.tool.started"),
            event("gateway.tool.completed", other)}), "session-1", "user:local").status, pixiu::AgentEvidenceResult::Invalid);
        auto items = result()["items"].toArray();
        auto item = items[0].toObject();
        item["evidence_ids"] = QJsonArray{"../../private"};
        other = result();
        other["items"] = QJsonArray{item};
        QCOMPARE(pixiu::parseAgentEvidence(response({event("gateway.tool.started"),
            event("gateway.tool.completed", other)}), "session-1", "user:local").status, pixiu::AgentEvidenceResult::Invalid);
    }
    void rejectsMalformedTraceAndCapsReferences() {
        auto bad = QJsonDocument(QJsonObject{{"session_id", "session-1"}, {"content", "{unfinished"}}).toJson();
        QCOMPARE(pixiu::parseAgentEvidence(bad, "session-1", "user:local").status, pixiu::AgentEvidenceResult::Invalid);
        auto item = result()["items"].toArray()[0].toObject();
        QJsonArray ids;
        for (int i = 0; i < 257; ++i) ids.append(QString("evd_example%1").arg(i));
        item["evidence_ids"] = ids;
        auto many = result();
        many["items"] = QJsonArray{item};
        const auto parsed = pixiu::parseAgentEvidence(response({event("gateway.tool.started"),
            event("gateway.tool.completed", many)}), "session-1", "user:local");
        QCOMPARE(parsed.status, pixiu::AgentEvidenceResult::TooLarge);
        QVERIFY(parsed.references.isEmpty());
    }
    void ignoresBranchAndOtherTools() {
        auto complete = event("gateway.tool.completed", result());
        auto data = complete["data"].toObject();
        data["scope"] = "branch";
        complete["data"] = data;
        QVERIFY(pixiu::parseAgentEvidence(response({event("gateway.tool.started"), complete}), "session-1", "user:local").references.isEmpty());
        data.remove("scope");
        data["name"] = "terminal";
        complete["data"] = data;
        QVERIFY(pixiu::parseAgentEvidence(response({event("gateway.tool.started"), complete}), "session-1", "user:local").references.isEmpty());
    }
};
QTEST_GUILESS_MAIN(AgentEvidenceTest)
#include "t_agent_evidence.moc"
