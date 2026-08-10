#include <QLabel>
#include <QLineEdit>
#include <QMouseEvent>
#include <QPushButton>
#include <QSignalSpy>
#include <QTest>

#include "services/BackendTypes.h"
#include "widgets/ChatWindow.h"
#include "widgets/InputBar.h"
#include "widgets/MessageList.h"

// ChatWindow 交互测试：显示/隐藏、后端状态、顶栏按钮、发送与输入恢复。
class TestChatWindow : public QObject
{
    Q_OBJECT

private slots:
    void messageListIsAvailable();
    void showAndFocusShowsWindow();
    void escapeHidesWindow();
    void backendStateUpdatesStatusLabel();
    void offlineStateDisablesInput();
    void panelButtonEmitsOpenPanelRequested();
    void settingsButtonEmitsSettingsRequested();
    void closeButtonEmitsCloseRequested();
    void buttonsHaveToolTips();
    void statusLabelHasStableMinimumWidth();
    void dragMovesWindowAndEmitsMoved();
    void buttonsHaveAccessibleNames();
    void defaultSizeIsNarrowTall();
    void welcomeShownInitiallyThenHiddenAfterMessage();
    void welcomeActionsForwardToWindowSignals();
    void sendButtonForwardsTextAndClears();
    void restoreInputPrefillsLineEdit();
};

void TestChatWindow::messageListIsAvailable()
{
    ChatWindow window;
    QVERIFY(window.messageList() != nullptr);
    QCOMPARE(window.messageList()->count(), 0);
}

void TestChatWindow::showAndFocusShowsWindow()
{
    ChatWindow window;
    QVERIFY(!window.isChatVisible());
    window.showAndFocus();
    QVERIFY(window.isChatVisible());
}

void TestChatWindow::escapeHidesWindow()
{
    ChatWindow window;
    window.showAndFocus();
    QTest::keyClick(&window, Qt::Key_Escape);
    QTRY_VERIFY(!window.isChatVisible());
}

void TestChatWindow::backendStateUpdatesStatusLabel()
{
    ChatWindow window;
    QLabel *status = window.findChild<QLabel *>(QStringLiteral("statusLabel"));
    QVERIFY(status != nullptr);

    window.setBackendState(ConnectionState::Connected);
    QCOMPARE(status->text(), QStringLiteral("● 在线"));
    window.setBackendState(ConnectionState::Connecting);
    QCOMPARE(status->text(), QStringLiteral("● 连接中…"));
    window.setBackendState(ConnectionState::Error);
    QCOMPARE(status->text(), QStringLiteral("● 服务异常"));
    window.setBackendState(ConnectionState::Disconnected);
    QCOMPARE(status->text(), QStringLiteral("● 离线"));
}

void TestChatWindow::offlineStateDisablesInput()
{
    ChatWindow window;
    InputBar *input = window.findChild<InputBar *>();
    QVERIFY(input != nullptr);

    window.setBackendState(ConnectionState::Connected);
    QVERIFY(input->isEnabled());
    window.setBackendState(ConnectionState::Disconnected);
    QVERIFY(!input->isEnabled());
    window.setBackendState(ConnectionState::Error);
    QVERIFY(!input->isEnabled());
}

void TestChatWindow::panelButtonEmitsOpenPanelRequested()
{
    ChatWindow window;
    QSignalSpy spy(&window, &ChatWindow::openPanelRequested);
    QPushButton *button =
        window.findChild<QPushButton *>(QStringLiteral("panelButton"));
    QVERIFY(button != nullptr);
    QTest::mouseClick(button, Qt::LeftButton);
    QCOMPARE(spy.count(), 1);
}

void TestChatWindow::settingsButtonEmitsSettingsRequested()
{
    ChatWindow window;
    QSignalSpy spy(&window, &ChatWindow::settingsRequested);
    QPushButton *button =
        window.findChild<QPushButton *>(QStringLiteral("settingsButton"));
    QVERIFY(button != nullptr);
    QTest::mouseClick(button, Qt::LeftButton);
    QCOMPARE(spy.count(), 1);
}

void TestChatWindow::closeButtonEmitsCloseRequested()
{
    ChatWindow window;
    QSignalSpy spy(&window, &ChatWindow::closeRequested);
    QPushButton *button =
        window.findChild<QPushButton *>(QStringLiteral("closeButton"));
    QVERIFY(button != nullptr);
    QTest::mouseClick(button, Qt::LeftButton);
    QCOMPARE(spy.count(), 1);
}

void TestChatWindow::buttonsHaveToolTips()
{
    ChatWindow window;
    QPushButton *settings =
        window.findChild<QPushButton *>(QStringLiteral("settingsButton"));
    QPushButton *panel =
        window.findChild<QPushButton *>(QStringLiteral("panelButton"));
    QPushButton *close =
        window.findChild<QPushButton *>(QStringLiteral("closeButton"));
    QVERIFY(settings != nullptr);
    QVERIFY(panel != nullptr);
    QVERIFY(close != nullptr);
    QVERIFY(!settings->toolTip().isEmpty());
    QVERIFY(!panel->toolTip().isEmpty());
    QVERIFY(!close->toolTip().isEmpty());
}

void TestChatWindow::statusLabelHasStableMinimumWidth()
{
    ChatWindow window;
    QLabel *status = window.findChild<QLabel *>(QStringLiteral("statusLabel"));
    QVERIFY(status != nullptr);

    // 最小宽度必须足以容纳最长状态文案，避免状态切换时顶栏布局抖动。
    const int widest = qMax(
        qMax(status->fontMetrics().horizontalAdvance(QStringLiteral("● 在线")),
             status->fontMetrics().horizontalAdvance(
                 QStringLiteral("● 连接中…"))),
        qMax(status->fontMetrics().horizontalAdvance(
                 QStringLiteral("● 服务异常")),
             status->fontMetrics().horizontalAdvance(QStringLiteral("● 离线"))));
    QVERIFY(status->minimumWidth() >= widest);
    QVERIFY(status->minimumWidth() > 0);
}

void TestChatWindow::dragMovesWindowAndEmitsMoved()
{
    ChatWindow window;
    window.show();
    QVERIFY(QTest::qWaitForWindowExposed(&window));

    const QPoint before = window.pos();
    QSignalSpy moved(&window, &ChatWindow::moved);
    // offscreen 平台下 QTest::mouseMove 不带按键状态，直接合成拖动事件。
    QMouseEvent press(QEvent::MouseButtonPress, QPoint(10, 10),
                      window.mapToGlobal(QPoint(10, 10)),
                      Qt::LeftButton, Qt::LeftButton, Qt::NoModifier);
    QApplication::sendEvent(&window, &press);

    QMouseEvent move(QEvent::MouseMove, QPoint(40, 35),
                     window.mapToGlobal(QPoint(40, 35)),
                     Qt::NoButton, Qt::LeftButton, Qt::NoModifier);
    QApplication::sendEvent(&window, &move);

    QMouseEvent release(QEvent::MouseButtonRelease, QPoint(40, 35),
                        window.mapToGlobal(QPoint(40, 35)),
                        Qt::LeftButton, Qt::NoButton, Qt::NoModifier);
    QApplication::sendEvent(&window, &release);

    QVERIFY(window.pos() != before);
    QVERIFY(moved.count() >= 1);
}

void TestChatWindow::buttonsHaveAccessibleNames()
{
    ChatWindow window;
    QPushButton *settings =
        window.findChild<QPushButton *>(QStringLiteral("settingsButton"));
    QPushButton *panel =
        window.findChild<QPushButton *>(QStringLiteral("panelButton"));
    QPushButton *close =
        window.findChild<QPushButton *>(QStringLiteral("closeButton"));
    QVERIFY(panel != nullptr);
    QVERIFY(close != nullptr);
    QVERIFY(settings != nullptr);
    QVERIFY(!settings->accessibleName().isEmpty());
    QVERIFY(!panel->accessibleName().isEmpty());
    QVERIFY(!close->accessibleName().isEmpty());
}

void TestChatWindow::defaultSizeIsNarrowTall()
{
    ChatWindow window;
    // 侧边助手形态：默认窄而高，最小尺寸保持窄高比例。
    QVERIFY(window.width() < window.height());
    QVERIFY(window.minimumWidth() < window.minimumHeight());
}

void TestChatWindow::welcomeShownInitiallyThenHiddenAfterMessage()
{
    ChatWindow window;
    window.show();
    QVERIFY(QTest::qWaitForWindowExposed(&window));

    QWidget *welcome =
        window.findChild<QWidget *>(QStringLiteral("welcomeView"));
    QVERIFY(welcome != nullptr);
    QVERIFY(welcome->isVisible());

    // 消息到达后切换到消息流，欢迎页隐藏。
    ChatMessage message;
    message.role = MessageRole::User;
    message.text = QStringLiteral("水电燃气花了多少钱？");
    message.timestamp = 1786164000;
    window.messageList()->appendMessage(message);
    QVERIFY(!welcome->isVisible());

    // 清空消息后回到欢迎页（行删除经零延迟定时器处理）。
    window.messageList()->clearMessages();
    QTRY_VERIFY(welcome->isVisible());
}

void TestChatWindow::welcomeActionsForwardToWindowSignals()
{
    ChatWindow window;
    window.show();
    QSignalSpy attachSpy(&window, &ChatWindow::attachRequested);
    QSignalSpy panelSpy(&window, &ChatWindow::openPanelRequested);

    const QList<QPushButton *> actions =
        window.findChildren<QPushButton *>(QStringLiteral("welcomeAction"));
    QCOMPARE(actions.size(), 3);

    // “录入知识”与“记忆面板”分别转发到窗口信号；“开始提问”聚焦输入框。
    for (QPushButton *action : actions) {
        if (action->text() == QStringLiteral("录入知识")) {
            QTest::mouseClick(action, Qt::LeftButton);
            QCOMPARE(attachSpy.count(), 1);
        } else if (action->text() == QStringLiteral("记忆面板")) {
            QTest::mouseClick(action, Qt::LeftButton);
            QCOMPARE(panelSpy.count(), 1);
        } else {
            QCOMPARE(action->text(), QStringLiteral("开始提问"));
        }
    }
}

void TestChatWindow::sendButtonForwardsTextAndClears()
{
    ChatWindow window;
    InputBar *input = window.findChild<InputBar *>();
    QLineEdit *lineEdit = input->findChild<QLineEdit *>(QStringLiteral("lineEdit"));
    QPushButton *send =
        input->findChild<QPushButton *>(QStringLiteral("sendButton"));
    QSignalSpy spy(&window, &ChatWindow::sendRequested);

    lineEdit->setText(QStringLiteral("水电燃气花了多少钱？"));
    QTest::mouseClick(send, Qt::LeftButton);

    QCOMPARE(spy.count(), 1);
    QCOMPARE(spy.takeFirst().at(0).toString(),
             QStringLiteral("水电燃气花了多少钱？"));
    QVERIFY(lineEdit->text().isEmpty());
}

void TestChatWindow::restoreInputPrefillsLineEdit()
{
    ChatWindow window;
    InputBar *input = window.findChild<InputBar *>();
    QLineEdit *lineEdit = input->findChild<QLineEdit *>(QStringLiteral("lineEdit"));

    window.restoreInput(QStringLiteral("失败后保留的输入"));
    QCOMPARE(lineEdit->text(), QStringLiteral("失败后保留的输入"));
}

QTEST_MAIN(TestChatWindow)
#include "t_chat_window.moc"
