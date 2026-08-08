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

QTEST_MAIN(TestFloatingBall)
#include "t_floating_ball.moc"
