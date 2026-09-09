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
    void dreamingReportsActualProgressWithoutExtraInteraction() {
        QWebSocketServer server("test", QWebSocketServer::NonSecureMode);
        QVERIFY(server.listen(QHostAddress::LocalHost, 0));
        pixiu::BackendEventStatus status(QString("http://127.0.0.1:%1").arg(server.serverPort()));
        QTRY_VERIFY(server.hasPendingConnections());
        auto *peer = server.nextPendingConnection();
        auto *label = status.findChild<QLabel *>("dreamingProgress");
        QVERIFY(label);
        peer->sendTextMessage(R"({"event":"dreaming_progress","data":{"status":"running","processed_blocks":1,"total_blocks":2,"saved_count":1,"name":"private-file"}})");
        QTRY_VERIFY(label->text().contains("50%"));
        QVERIFY(!label->text().contains("private-file"));
        peer->sendTextMessage(R"({"event":"dreaming_progress","data":{"status":"incomplete","processed_blocks":1,"total_blocks":2,"saved_count":1}})");
        QTRY_VERIFY(label->text().contains(QStringLiteral("尚未完整整理")));
        QVERIFY(status.findChildren<QDialog *>().isEmpty());
        peer->close();
        peer->deleteLater();
    }
    void invalidFramesCannotDriveWorkspaceActions() {
        QWebSocketServer server("test", QWebSocketServer::NonSecureMode);
        QVERIFY(server.listen(QHostAddress::LocalHost, 0));
        pixiu::BackendEventStatus status(QString("http://127.0.0.1:%1").arg(server.serverPort()));
        QSignalSpy changed(&status, &pixiu::BackendEventStatus::dataChanged);
        QSignalSpy attention(&status, &pixiu::BackendEventStatus::conflictAttentionRequested);
        QTRY_VERIFY(server.hasPendingConnections());
        auto *peer = server.nextPendingConnection();
        QSignalSpy commands(peer, &QWebSocket::textMessageReceived);
        QTRY_VERIFY(!changed.isEmpty());
        changed.clear();
        const QStringList invalid{
            QStringLiteral("not-json"), QStringLiteral("[]"),
            QStringLiteral(R"({"data":{"severity":"high"}})"),
            QStringLiteral(R"({"event":"capture_event"})"),
            QStringLiteral(R"({"event":"conflict_detected","data":null})"),
            QStringLiteral(R"({"event":"sync_event","data":[]})"),
            QStringLiteral(R"({"event":"pair_request","data":"private-secret"})"),
            QStringLiteral(R"({"event":"future_private_event","data":{"severity":"high"}})"),
            QStringLiteral(R"({"event":"forget_request","data":{"command":"private-secret"}})")};
        for (const auto &frame : invalid) peer->sendTextMessage(frame);
        // Same socket, ordered frames: the valid event is a processing barrier.
        peer->sendTextMessage(R"({"event":"capture_event","data":{}})");
        QTRY_COMPARE(changed.count(), 1);
        QCOMPARE(changed.first().first().toString(), QStringLiteral("capture_event"));
        QVERIFY(!status.findChild<QPushButton *>("eventDismiss"));
        QVERIFY(status.findChild<QLabel *>("eventConnection")->text().isEmpty());
        QCOMPARE(attention.count(), 0);
        QCOMPARE(commands.count(), 0);
        QVERIFY(status.findChildren<QDialog *>().isEmpty());
        peer->close();
        peer->deleteLater();
    }
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
        QCOMPARE(attention.count(), 0);
        QCOMPARE(sentCommands.count(), 0);
        QVERIFY(status.findChildren<QDialog *>().isEmpty());
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
        QTRY_VERIFY(!changed.isEmpty());
        QCOMPARE(changed.takeFirst().at(0).toString(), QStringLiteral("reconnected"));
        peer->sendTextMessage(R"({"event":"forget_confirmation","data":{"command":"secret-command","confirmation_token":"secret-token"}})");
        QTRY_VERIFY(!changed.isEmpty());
        QCOMPARE(changed.takeFirst().at(0).toString(), QStringLiteral("forget_confirmation"));
        QVERIFY(status.findChildren<QDialog *>().isEmpty());
        auto *review = status.findChild<QPushButton *>("reviewAgentForget");
        QVERIFY(review);
        QVERIFY(review->isHidden());
        peer->sendTextMessage(R"({"event":"forget_requested","data":{"command":"忘记测试记忆","scope":"user:default"}})");
        QTRY_VERIFY(!review->isHidden());
        QVERIFY(status.findChildren<QDialog *>().isEmpty());
        QCOMPARE(sentCommands.count(), 0);
        peer->sendTextMessage(R"({"event":"forget_confirmation","data":{}})");
        peer->sendTextMessage(R"({"event":"capture_event","data":{}})");
        peer->abort();
        peer->deleteLater();
        QTRY_VERIFY_WITH_TIMEOUT(server.hasPendingConnections(), 8000);
        auto *replacement = server.nextPendingConnection();
        QTRY_VERIFY(status.findChild<QLabel *>("eventConnection")->text().isEmpty());
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
        peer->sendTextMessage(QStringLiteral("{\"event\":\"memory_ready\",\"data\":{\"text\":\"")
            + QString(2 * 1024 * 1024, QLatin1Char('x')) + QStringLiteral("\"}}"));
        QTRY_VERIFY_WITH_TIMEOUT(!disconnected.isEmpty(), 8000);
        peer->deleteLater();
    }
    void invalidAddressDoesNotConnect() {
        pixiu::BackendEventStatus status("http://user:secret@localhost:1234/?token=secret");
        QVERIFY(status.findChild<QLabel *>("eventConnection")->text().contains(QStringLiteral("无法连接")));
        QVERIFY(!status.findChild<QLabel *>("eventConnection")->text().contains("secret"));
    }
};
QTEST_MAIN(BackendEventsTest)
#include "t_backend_events.moc"
