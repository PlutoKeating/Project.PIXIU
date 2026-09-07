#include "BackendEventStatus.h"
#include <QDialog>
#include <QLabel>
#include <QPushButton>
#include <QSignalSpy>
#include <QTest>
#include <QWebSocket>
#include <QWebSocketServer>

class BackendEventsTest : public QObject {
    Q_OBJECT
private slots:
    void notificationsNeverBecomeConfirmation() {
        QWebSocketServer server("test", QWebSocketServer::NonSecureMode);
        QVERIFY(server.listen(QHostAddress::LocalHost, 0));
        pixiu::BackendEventStatus status(QString("http://127.0.0.1:%1").arg(server.serverPort()));
        QTRY_VERIFY(server.hasPendingConnections());
        auto *peer = server.nextPendingConnection();
        QSignalSpy sentCommands(peer, &QWebSocket::textMessageReceived);
        auto *notice = status.findChild<QLabel *>("eventChanges");
        auto *dismiss = status.findChild<QPushButton *>("eventDismiss");
        QTRY_VERIFY(dismiss->isEnabled());
        dismiss->click();
        peer->sendTextMessage(R"({"event":"forget_confirmation","data":{"command":"secret-command","confirmation_token":"secret-token"}})");
        QTRY_VERIFY(notice->text().contains(QStringLiteral("记忆")));
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
