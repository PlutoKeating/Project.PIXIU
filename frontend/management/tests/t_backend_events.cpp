#include "BackendEventStatus.h"
#include <QDialog>
#include <QJsonDocument>
#include <QJsonObject>
#include <QLabel>
#include <QPushButton>
#include <QSignalSpy>
#include <QTest>
#include <QWebSocket>
#include <QWebSocketServer>

class BackendEventsTest : public QObject {
    Q_OBJECT
private slots:
    void captureChangesDoNotInferRelationsOrExposeSourceText() {
        QWebSocketServer server("test", QWebSocketServer::NonSecureMode);
        QVERIFY(server.listen(QHostAddress::LocalHost, 0));
        pixiu::BackendEventStatus status(QString("http://127.0.0.1:%1").arg(server.serverPort()));
        QSignalSpy changed(&status, &pixiu::BackendEventStatus::dataChanged);
        QSignalSpy attention(&status, &pixiu::BackendEventStatus::conflictAttentionRequested);
        QTRY_VERIFY(server.hasPendingConnections());
        auto *peer = server.nextPendingConnection();
        QSignalSpy sentCommands(peer, &QWebSocket::textMessageReceived);
        QTRY_VERIFY(!changed.isEmpty());
        changed.clear();
        auto *notice = status.findChild<QLabel *>("eventChanges");
        auto *dismiss = status.findChild<QPushButton *>("eventDismiss");
        dismiss->click();
        const QStringList states{QStringLiteral("ingested"), QStringLiteral("sensitive_quarantined"),
                                 QStringLiteral("ignored"), QStringLiteral("state_changed")};
        for (const QString &state : states) {
            const QJsonObject data{{"source", "directory"}, {"status", state},
                {"summary", "private-filename.txt"}, {"title", "private-topic"},
                {"severity", "high"}, {"evidence_id", "private-evidence"}};
            peer->sendTextMessage(QString::fromUtf8(QJsonDocument(QJsonObject{
                {"event", "capture_event"}, {"data", data}}).toJson(QJsonDocument::Compact)));
        }
        QTRY_COMPARE(changed.count(), states.size());
        for (const auto &args : changed) {
            QCOMPARE(args.size(), 1);
            QCOMPARE(args.first().toString(), QStringLiteral("capture_event"));
        }
        QCOMPARE(notice->text().count(QStringLiteral("采集与隐私")), 1);
        QVERIFY(!notice->text().contains("private"));
        QVERIFY(!notice->text().contains(QStringLiteral("相关")));
        QCOMPARE(attention.count(), 0);
        QCOMPARE(sentCommands.count(), 0);
        QVERIFY(status.findChildren<QDialog *>().isEmpty());
        dismiss->click();
        QVERIFY(notice->text().isEmpty());
        QCOMPARE(changed.count(), states.size());
        peer->close();
        peer->deleteLater();
    }
    void onlySevereConflictsRequestBoundedPayloadFreeAttention() {
        QWebSocketServer server("test", QWebSocketServer::NonSecureMode);
        QVERIFY(server.listen(QHostAddress::LocalHost, 0));
        pixiu::BackendEventStatus status(QString("http://127.0.0.1:%1").arg(server.serverPort()));
        QSignalSpy attention(&status, &pixiu::BackendEventStatus::conflictAttentionRequested);
        QSignalSpy changed(&status, &pixiu::BackendEventStatus::dataChanged);
        QTRY_VERIFY(server.hasPendingConnections());
        auto *peer = server.nextPendingConnection();
        QTRY_VERIFY(!changed.isEmpty());
        changed.clear();
        peer->sendTextMessage(R"({"event":"conflict_detected","data":{"severity":"medium"}})");
        peer->sendTextMessage(R"({"event":"conflict_detected","data":{"severity":"unknown"}})");
        peer->sendTextMessage(R"({"event":"forget_confirmation","data":{"severity":"high"}})");
        QTRY_COMPARE(changed.count(), 3);
        QCOMPARE(attention.count(), 0);
        for (int i = 0; i < 20; ++i)
            peer->sendTextMessage(R"({"event":"conflict_detected","data":{"severity":" HIGH ","old_value":"private-secret"}})");
        QTRY_COMPARE(changed.count(), 23);
        QCOMPARE(attention.count(), 1);
        QVERIFY(attention.first().isEmpty());
        QVERIFY(!status.findChild<QLabel *>("eventChanges")->text().contains("private-secret"));
        QVERIFY(status.findChildren<QDialog *>().isEmpty());
        peer->close();
        peer->deleteLater();
    }
    void notificationsNeverBecomeConfirmation() {
        QWebSocketServer server("test", QWebSocketServer::NonSecureMode);
        QVERIFY(server.listen(QHostAddress::LocalHost, 0));
        pixiu::BackendEventStatus status(QString("http://127.0.0.1:%1").arg(server.serverPort()));
        QSignalSpy changed(&status, &pixiu::BackendEventStatus::dataChanged);
        QTRY_VERIFY(server.hasPendingConnections());
        auto *peer = server.nextPendingConnection();
        QSignalSpy sentCommands(peer, &QWebSocket::textMessageReceived);
        auto *notice = status.findChild<QLabel *>("eventChanges");
        auto *dismiss = status.findChild<QPushButton *>("eventDismiss");
        QTRY_VERIFY(dismiss->isEnabled());
        QTRY_VERIFY(!changed.isEmpty());
        QCOMPARE(changed.takeFirst().at(0).toString(), QStringLiteral("reconnected"));
        dismiss->click();
        peer->sendTextMessage(R"({"event":"forget_confirmation","data":{"command":"secret-command","confirmation_token":"secret-token"}})");
        QTRY_VERIFY(notice->text().contains(QStringLiteral("记忆")));
        QCOMPARE(changed.takeFirst().at(0).toString(), QStringLiteral("forget_confirmation"));
        QVERIFY(!notice->text().contains("secret"));
        QVERIFY(status.findChildren<QDialog *>().isEmpty());
        QCOMPARE(status.findChildren<QPushButton *>().size(), 1);
        QCOMPARE(sentCommands.count(), 0);
        peer->sendTextMessage(R"({"event":"forget_confirmation","data":{}})");
        peer->sendTextMessage(R"({"event":"capture_event","data":{}})");
        QTRY_VERIFY(notice->text().contains(QStringLiteral("采集与隐私")));
        QCOMPARE(notice->text().count(QStringLiteral("记忆")), 1);
        peer->abort();
        peer->deleteLater();
        QTRY_VERIFY_WITH_TIMEOUT(server.hasPendingConnections(), 8000);
        auto *replacement = server.nextPendingConnection();
        QTRY_VERIFY(notice->text().contains(QStringLiteral("连接恢复")));
        replacement->close();
        replacement->deleteLater();
    }
    void oversizedEventIsNotDisplayed() {
#if QT_VERSION < QT_VERSION_CHECK(5, 15, 0)
        QSKIP("Qt before 5.15 only supports the post-assembly parser limit");
#endif
        QWebSocketServer server("test", QWebSocketServer::NonSecureMode);
        QVERIFY(server.listen(QHostAddress::LocalHost, 0));
        pixiu::BackendEventStatus status(QString("http://127.0.0.1:%1").arg(server.serverPort()));
        QTRY_VERIFY(server.hasPendingConnections());
        auto *peer = server.nextPendingConnection();
        QSignalSpy disconnected(peer, &QWebSocket::disconnected);
        QTRY_VERIFY(status.findChild<QPushButton *>("eventDismiss")->isEnabled());
        status.findChild<QPushButton *>("eventDismiss")->click();
        peer->sendTextMessage(QStringLiteral("{\"event\":\"memory_ready\",\"data\":{\"text\":\"")
            + QString(2 * 1024 * 1024, QLatin1Char('x')) + QStringLiteral("\"}}"));
        QTRY_VERIFY_WITH_TIMEOUT(!disconnected.isEmpty(), 8000);
        QVERIFY(!status.findChild<QLabel *>("eventChanges")->text().contains(QStringLiteral("记忆")));
        peer->deleteLater();
    }
    void invalidAddressDoesNotConnect() {
        pixiu::BackendEventStatus status("http://user:secret@localhost:1234/?token=secret");
        QVERIFY(status.findChild<QLabel *>("eventConnection")->text().contains(QStringLiteral("地址无效")));
        QVERIFY(!status.findChild<QLabel *>("eventConnection")->text().contains("secret"));
    }
};
QTEST_MAIN(BackendEventsTest)
#include "t_backend_events.moc"
