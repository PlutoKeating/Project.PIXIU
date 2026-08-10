#include <QAction>
#include <QLabel>
#include <QMenu>
#include <QMouseEvent>
#include <QPlainTextEdit>
#include <QPushButton>
#include <QSignalSpy>
#include <QTest>

#include "services/BackendTypes.h"
#include "widgets/ChatWindow.h"
#include "widgets/InputBar.h"
#include "widgets/MessageList.h"

// ChatWindow 交互测试：显示/隐藏、后端状态 badge、顶栏置顶/关闭、
// 发送与输入恢复、欢迎页建议卡片。
class TestChatWindow : public QObject
{
    Q_OBJECT

private slots:
    void messageListIsAvailable();
    void showAndFocusShowsWindow();
    void escapeHidesWindow();
    void backendStateUpdatesInputBadge();
    void offlineStateDisablesEditorButKeepsChips();
    void pinButtonTogglesAlwaysOnTop();
    void topBarHasNoDuplicateFunctionMenu();
    void closeButtonEmitsCloseRequested();
    void buttonsHaveToolTipsAndAccessibleNames();
    void dragMovesWindowAndEmitsMoved();
    void defaultSizeIsNarrowTall();
    void welcomeShownInitiallyThenHiddenAfterMessage();
    void suggestionCardsFillInput();
    void sendButtonForwardsTextAndClears();
    void restoreInputPrefillsEditor();
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

void TestChatWindow::backendStateUpdatesInputBadge()
{
    ChatWindow window;
    InputBar *input = window.findChild<InputBar *>();
    QVERIFY(input != nullptr);
    QLabel *badge = input->findChild<QLabel *>(
        QStringLiteral("inputStateBadge"));
    QVERIFY(badge != nullptr);

    window.setBackendState(ConnectionState::Connected);
    QCOMPARE(badge->text(), QStringLiteral("● 在线"));
    window.setBackendState(ConnectionState::Connecting);
    QCOMPARE(badge->text(), QStringLiteral("● 连接中…"));
    window.setBackendState(ConnectionState::Error);
    QCOMPARE(badge->text(), QStringLiteral("● 服务异常"));
    window.setBackendState(ConnectionState::Disconnected);
    QCOMPARE(badge->text(), QStringLiteral("● 离线"));
}

void TestChatWindow::offlineStateDisablesEditorButKeepsChips()
{
    ChatWindow window;
    InputBar *input = window.findChild<InputBar *>();
    QVERIFY(input != nullptr);
    QPlainTextEdit *editor = input->findChild<QPlainTextEdit *>(
        QStringLiteral("inputEdit"));
    QPushButton *memoryChip = input->findChild<QPushButton *>(
        QStringLiteral("memoryChip"));
    QVERIFY(editor != nullptr);
    QVERIFY(memoryChip != nullptr);

    window.setBackendState(ConnectionState::Connected);
    QVERIFY(editor->isEnabled());
    window.setBackendState(ConnectionState::Disconnected);
    QVERIFY(!editor->isEnabled());
    window.setBackendState(ConnectionState::Error);
    QVERIFY(!editor->isEnabled());
    // 离线时记忆/设置等入口仍需可用（不把整条输入栏一起禁掉）。
    QVERIFY(memoryChip->isEnabled());
}

void TestChatWindow::pinButtonTogglesAlwaysOnTop()
{
    ChatWindow window;
    window.show();
    QPushButton *pin =
        window.findChild<QPushButton *>(QStringLiteral("pinButton"));
    QVERIFY(pin != nullptr);

    QTest::mouseClick(pin, Qt::LeftButton);
    QVERIFY(window.windowFlags() & Qt::WindowStaysOnTopHint);
    QTest::mouseClick(pin, Qt::LeftButton);
    QVERIFY(!(window.windowFlags() & Qt::WindowStaysOnTopHint));
}

void TestChatWindow::topBarHasNoDuplicateFunctionMenu()
{
    // 功能入口统一收敛到 chip 行，顶栏不再提供重复的“更多”功能菜单。
    ChatWindow window;
    QVERIFY(window.findChild<QPushButton *>(QStringLiteral("moreButton"))
            == nullptr);
    QVERIFY(window.findChild<QMenu *>(QStringLiteral("topBarMenu"))
            == nullptr);
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

void TestChatWindow::buttonsHaveToolTipsAndAccessibleNames()
{
    ChatWindow window;
    QPushButton *pin =
        window.findChild<QPushButton *>(QStringLiteral("pinButton"));
    QPushButton *close =
        window.findChild<QPushButton *>(QStringLiteral("closeButton"));
    QVERIFY(pin != nullptr);
    QVERIFY(close != nullptr);
    QVERIFY(!pin->toolTip().isEmpty());
    QVERIFY(!close->toolTip().isEmpty());
    QVERIFY(!pin->accessibleName().isEmpty());
    QVERIFY(!close->accessibleName().isEmpty());
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

void TestChatWindow::suggestionCardsFillInput()
{
    ChatWindow window;
    window.show();
    InputBar *input = window.findChild<InputBar *>();
    QPlainTextEdit *editor = input->findChild<QPlainTextEdit *>(
        QStringLiteral("inputEdit"));
    const QList<QPushButton *> cards =
        window.findChildren<QPushButton *>(QStringLiteral("suggestionCard"));
    QCOMPARE(cards.size(), 4);

    QTest::mouseClick(cards.first(), Qt::LeftButton);
    QVERIFY(!editor->toPlainText().isEmpty());
}

void TestChatWindow::sendButtonForwardsTextAndClears()
{
    ChatWindow window;
    InputBar *input = window.findChild<InputBar *>();
    QPlainTextEdit *editor = input->findChild<QPlainTextEdit *>(
        QStringLiteral("inputEdit"));
    QPushButton *send =
        input->findChild<QPushButton *>(QStringLiteral("sendButton"));
    QSignalSpy spy(&window, &ChatWindow::sendRequested);

    window.setBackendState(ConnectionState::Connected);
    editor->setPlainText(QStringLiteral("水电燃气花了多少钱？"));
    QTest::mouseClick(send, Qt::LeftButton);

    QCOMPARE(spy.count(), 1);
    QCOMPARE(spy.takeFirst().at(0).toString(),
             QStringLiteral("水电燃气花了多少钱？"));
    QVERIFY(editor->toPlainText().isEmpty());
}

void TestChatWindow::restoreInputPrefillsEditor()
{
    ChatWindow window;
    InputBar *input = window.findChild<InputBar *>();
    QPlainTextEdit *editor = input->findChild<QPlainTextEdit *>(
        QStringLiteral("inputEdit"));

    window.restoreInput(QStringLiteral("失败后保留的输入"));
    QCOMPARE(editor->toPlainText(), QStringLiteral("失败后保留的输入"));
}

QTEST_MAIN(TestChatWindow)
#include "t_chat_window.moc"
