#include <QAction>
#include <QApplication>
#include <QGuiApplication>
#include <QMenu>
#include <QMouseEvent>
#include <QScreen>
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
    void clickWithoutDragEmitsClicked();
    void dragMovesBallAndEmitsMoved();
    void dropNearEdgeKeepsBallFullyVisible();
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

void TestFloatingBall::clickWithoutDragEmitsClicked()
{
    FloatingBall ball;
    ball.show();
    QVERIFY(QTest::qWaitForWindowExposed(&ball));

    QSignalSpy clicked(&ball, &FloatingBall::clicked);
    QSignalSpy moved(&ball, &FloatingBall::movedTo);

    const QPoint center(ball.width() / 2, ball.height() / 2);
    QMouseEvent press(QEvent::MouseButtonPress, center, ball.mapToGlobal(center),
                      Qt::LeftButton, Qt::LeftButton, Qt::NoModifier);
    QApplication::sendEvent(&ball, &press);
    QMouseEvent release(QEvent::MouseButtonRelease, center, ball.mapToGlobal(center),
                        Qt::LeftButton, Qt::NoButton, Qt::NoModifier);
    QApplication::sendEvent(&ball, &release);

    QCOMPARE(clicked.count(), 1);
    QCOMPARE(moved.count(), 0);
}

void TestFloatingBall::dragMovesBallAndEmitsMoved()
{
    FloatingBall ball;
    ball.show();
    QVERIFY(QTest::qWaitForWindowExposed(&ball));

    const QPoint before = ball.pos();
    QSignalSpy clicked(&ball, &FloatingBall::clicked);
    QSignalSpy moved(&ball, &FloatingBall::movedTo);

    // offscreen 平台下 QTest::mouseMove 不带按键状态，直接合成拖动事件。
    const QPoint from(12, 12);
    const QPoint to(48, 40);
    QMouseEvent press(QEvent::MouseButtonPress, from, ball.mapToGlobal(from),
                      Qt::LeftButton, Qt::LeftButton, Qt::NoModifier);
    QApplication::sendEvent(&ball, &press);
    QMouseEvent move(QEvent::MouseMove, to, ball.mapToGlobal(to),
                     Qt::NoButton, Qt::LeftButton, Qt::NoModifier);
    QApplication::sendEvent(&ball, &move);
    QMouseEvent release(QEvent::MouseButtonRelease, to, ball.mapToGlobal(to),
                        Qt::LeftButton, Qt::NoButton, Qt::NoModifier);
    QApplication::sendEvent(&ball, &release);

    QVERIFY(ball.pos() != before);
    QCOMPARE(clicked.count(), 0);
    QVERIFY(moved.count() >= 1);
    // 拖动后小球保持完整尺寸（不贴边收起）。
    QCOMPARE(ball.width(), FloatingBall::kSize);
    QCOMPARE(ball.height(), FloatingBall::kSize);
}

void TestFloatingBall::dropNearEdgeKeepsBallFullyVisible()
{
    FloatingBall ball;
    ball.show();
    QVERIFY(QTest::qWaitForWindowExposed(&ball));

    QScreen *screen = QGuiApplication::primaryScreen();
    QVERIFY(screen != nullptr);
    const QRect area = screen->availableGeometry();

    // 先拖到屏幕右边缘附近（贴边 1px），再拖动一段位移后释放：
    // 小球应停留在放置位置，而不是自动收起露出 1/3。
    ball.move(area.right() - ball.width() + 1,
              area.bottom() - ball.height() + 1);

    const QPoint from(10, 10);
    const QPoint to(14, 14); // 位移超过 4px 拖动阈值
    QMouseEvent press(QEvent::MouseButtonPress, from, ball.mapToGlobal(from),
                      Qt::LeftButton, Qt::LeftButton, Qt::NoModifier);
    QApplication::sendEvent(&ball, &press);
    QMouseEvent move(QEvent::MouseMove, to, ball.mapToGlobal(to),
                     Qt::NoButton, Qt::LeftButton, Qt::NoModifier);
    QApplication::sendEvent(&ball, &move);
    QMouseEvent release(QEvent::MouseButtonRelease, to, ball.mapToGlobal(to),
                        Qt::LeftButton, Qt::NoButton, Qt::NoModifier);
    QApplication::sendEvent(&ball, &release);

    // 完整停靠在放置位置：x 只随拖拽位移移动，且宽度保持完整。
    QCOMPARE(ball.x(), area.right() - ball.width() + 1 + (to.x() - from.x()));
    QCOMPARE(ball.width(), FloatingBall::kSize);
}

QTEST_MAIN(TestFloatingBall)
#include "t_floating_ball.moc"
