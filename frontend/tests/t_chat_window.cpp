#include <QLabel>
#include <QLineEdit>
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
    void closeButtonEmitsCloseRequested();
    void buttonsHaveAccessibleNames();
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

void TestChatWindow::buttonsHaveAccessibleNames()
{
    ChatWindow window;
    QPushButton *panel =
        window.findChild<QPushButton *>(QStringLiteral("panelButton"));
    QPushButton *close =
        window.findChild<QPushButton *>(QStringLiteral("closeButton"));
    QVERIFY(panel != nullptr);
    QVERIFY(close != nullptr);
    QVERIFY(!panel->accessibleName().isEmpty());
    QVERIFY(!close->accessibleName().isEmpty());
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
