#include "services/HttpBackendTransport.h"
#include <QJsonDocument>
#include <QSignalSpy>
#include <QTcpServer>
#include <QTcpSocket>
#include <QTest>

class UpdateTransportTest : public QObject
{
    Q_OBJECT
private slots:
    void preservesPayloadAndConflict()
    {
        QTcpServer server;
        QVERIFY(server.listen(QHostAddress::LocalHost));
        const auto previous = qgetenv("PIXIU_BACKEND_URL");
        const bool wasSet = qEnvironmentVariableIsSet("PIXIU_BACKEND_URL");
        qputenv("PIXIU_BACKEND_URL", QByteArray("http://127.0.0.1:") + QByteArray::number(server.serverPort()));
        HttpBackendTransport transport;
        if (wasSet) qputenv("PIXIU_BACKEND_URL", previous);
        else qunsetenv("PIXIU_BACKEND_URL");
        QList<QByteArray> paths;
        QList<QJsonObject> requests;
        bool conflict = false;
        connect(&server, &QTcpServer::newConnection, this, [&]() {
            auto *socket = server.nextPendingConnection();
            connect(socket, &QTcpSocket::readyRead, socket, [&, socket, buffer = QByteArray()]() mutable {
                buffer += socket->readAll();
                const int split = buffer.indexOf("\r\n\r\n");
                if (split < 0) return;
                const auto headers = buffer.left(split).split('\n');
                int length = -1;
                for (const auto &header : headers)
                    if (header.toLower().startsWith("content-length:")) length = header.mid(15).trimmed().toInt();
                if (length < 0 || buffer.size() < split + 4 + length) return;
                paths << headers.first().split(' ').value(1);
                requests << QJsonDocument::fromJson(buffer.mid(split + 4, length)).object();
                QByteArray body;
                if (conflict) body = R"({"detail":"VERSION_CONFLICT"})";
                else if (paths.last() == "/agent/context")
                    body = R"({"items":[{"knowledge_id":"knw_example01","version":7,"scope":"user:local"}],"truncated":false})";
                else body = R"({"knowledge_id":"knw_example01","version":8,"evidence_id":"evd_example01","status":"updated"})";
                socket->write(QByteArray("HTTP/1.1 ") + (conflict ? "409 Conflict" : "200 OK")
                    + "\r\nContent-Type: application/json\r\nConnection: close\r\nContent-Length: "
                    + QByteArray::number(body.size()) + "\r\n\r\n" + body);
                socket->disconnectFromHost();
                buffer.clear();
            });
        });
        QSignalSpy recalled(&transport, &BackendTransport::memoryContextResult);
        QSignalSpy updated(&transport, &BackendTransport::memoryUpdated);
        QSignalSpy errors(&transport, &BackendTransport::errorOccurred);
        const QJsonObject context{{"query", "example"}, {"scope", "user:local"},
            {"session_id", "desktop-edit"}, {"turn_id", "lookup-1"}, {"top_k", 5}};
        transport.memoryContext(context);
        QTRY_COMPARE(recalled.count(), 1);
        QCOMPARE(paths.last(), QByteArray("/agent/context"));
        QCOMPARE(requests.last(), context);
        const QJsonObject payload{{"knowledge_id", "knw_example01"}, {"expected_version", 7},
            {"scope", "user:local"}, {"title", "revised"},
            {"body", QJsonObject{{"text", "完整正文"}, {"nested", QJsonObject{{"keep", true}}}}},
            {"idempotency_key", "edit-1"}};
        transport.updateMemory(payload);
        QTRY_COMPARE(updated.count(), 1);
        QCOMPARE(paths.last(), QByteArray("/memory/update"));
        QCOMPARE(requests.last(), payload);
        QCOMPARE(updated.first().first().toJsonObject().value("version").toInt(), 8);
        conflict = true;
        transport.updateMemory(payload);
        QTRY_COMPARE(errors.count(), 1);
        QCOMPARE(errors.first().at(0).toString(), QStringLiteral("VERSION_CONFLICT"));
        QCOMPARE(updated.count(), 1);
        QCOMPARE(requests.last(), payload);
        QCOMPARE(requests.size(), 3); // No automatic stale-version retry.
    }
};
QTEST_MAIN(UpdateTransportTest)
#include "t_memory_update_transport.moc"
