#include <QAction>
#include <QMenu>
#include <QSignalSpy>
#include <QTest>

#include "widgets/FloatingBall.h"

// FloatingBall 未读角标 API 测试。
class TestFloatingBall : public QObject
{
    Q_OBJECT

private slots:
    void unreadStartsAtZero();
    void unreadCanBeSetAndCleared();
    void unreadClampsNegative();
    void contextMenuActionsEmitSignals();
};

void TestFloatingBall::unreadStartsAtZero()
{
    FloatingBall ball;
    QCOMPARE(ball.unreadCount(), 0);
}

void TestFloatingBall::unreadCanBeSetAndCleared()
{
    FloatingBall ball;
    ball.setUnreadCount(3);
    QCOMPARE(ball.unreadCount(), 3);
    ball.setUnreadCount(1);
    QCOMPARE(ball.unreadCount(), 1);
    ball.clearUnread();
    QCOMPARE(ball.unreadCount(), 0);
}

void TestFloatingBall::unreadClampsNegative()
{
    FloatingBall ball;
    ball.setUnreadCount(-5);
    QCOMPARE(ball.unreadCount(), 0);
}

void TestFloatingBall::contextMenuActionsEmitSignals()
{
    FloatingBall ball;
    QVERIFY(ball.findChild<QMenu *>() != nullptr);

    QSignalSpy clicked(&ball, &FloatingBall::clicked);
    QSignalSpy settings(&ball, &FloatingBall::settingsRequested);
    QSignalSpy panel(&ball, &FloatingBall::openPanelRequested);
    QSignalSpy quit(&ball, &FloatingBall::quitRequested);

    QAction *toggle = ball.findChild<QAction *>(QStringLiteral("toggleChatAction"));
    QAction *settingsAction =
        ball.findChild<QAction *>(QStringLiteral("settingsAction"));
    QAction *panelAction =
        ball.findChild<QAction *>(QStringLiteral("openPanelAction"));
    QAction *quitAction = ball.findChild<QAction *>(QStringLiteral("quitAction"));
    QVERIFY(toggle != nullptr);
    QVERIFY(settingsAction != nullptr);
    QVERIFY(panelAction != nullptr);
    QVERIFY(quitAction != nullptr);

    toggle->trigger();
    QCOMPARE(clicked.count(), 1);
    settingsAction->trigger();
    QCOMPARE(settings.count(), 1);
    panelAction->trigger();
    QCOMPARE(panel.count(), 1);
    quitAction->trigger();
    QCOMPARE(quit.count(), 1);
}

QTEST_MAIN(TestFloatingBall)
#include "t_floating_ball.moc"
