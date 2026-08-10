#include <QAction>
#include <QLabel>
#include <QMenu>
#include <QPlainTextEdit>
#include <QPushButton>
#include <QSignalSpy>
#include <QTest>

#include "services/BackendTypes.h"
#include "widgets/InputBar.h"

// InputBar 交互测试：发送/回车/换行/附件/空文本/输入恢复、chip 快捷入口、
// 状态 badge、空间不足时 chip 收缩进“更多”。
class TestInputBar : public QObject
{
    Q_OBJECT

private slots:
    void emptyTextDoesNotEmit();
    void typingEnablesSendButton();
    void sendEmitsAndClears();
    void returnKeyEmitsAndShiftReturnInsertsNewline();
    void attachButtonEmits();
    void setInputTextPrefills();
    void controlsHaveAccessibleNames();
    void chipsEmitSignals();
    void moreMenuEmitsSignals();
    void backendStateUpdatesBadgeAndAvailability();
    void chipsCollapseIntoMoreWhenNarrow();
};

void TestInputBar::emptyTextDoesNotEmit()
{
    InputBar bar;
    QSignalSpy spy(&bar, &InputBar::sendRequested);
    QPushButton *send =
        bar.findChild<QPushButton *>(QStringLiteral("sendButton"));
    QVERIFY(send != nullptr);
    QVERIFY(!send->isEnabled());
    QTest::mouseClick(send, Qt::LeftButton);
    QCOMPARE(spy.count(), 0);
}

void TestInputBar::typingEnablesSendButton()
{
    InputBar bar;
    QPlainTextEdit *editor =
        bar.findChild<QPlainTextEdit *>(QStringLiteral("inputEdit"));
    QPushButton *send =
        bar.findChild<QPushButton *>(QStringLiteral("sendButton"));
    bar.setBackendState(ConnectionState::Connected);

    editor->setPlainText(QStringLiteral("  "));
    QVERIFY(!send->isEnabled());
    editor->setPlainText(QStringLiteral("问题"));
    QVERIFY(send->isEnabled());
    editor->clear();
    QVERIFY(!send->isEnabled());
}

void TestInputBar::sendEmitsAndClears()
{
    InputBar bar;
    QPlainTextEdit *editor =
        bar.findChild<QPlainTextEdit *>(QStringLiteral("inputEdit"));
    QPushButton *send =
        bar.findChild<QPushButton *>(QStringLiteral("sendButton"));
    QSignalSpy spy(&bar, &InputBar::sendRequested);
    bar.setBackendState(ConnectionState::Connected);

    editor->setPlainText(QStringLiteral("  发送内容  "));
    QTest::mouseClick(send, Qt::LeftButton);

    QCOMPARE(spy.count(), 1);
    QCOMPARE(spy.takeFirst().at(0).toString(), QStringLiteral("发送内容"));
    QVERIFY(editor->toPlainText().isEmpty());
}

void TestInputBar::returnKeyEmitsAndShiftReturnInsertsNewline()
{
    InputBar bar;
    QPlainTextEdit *editor =
        bar.findChild<QPlainTextEdit *>(QStringLiteral("inputEdit"));
    QSignalSpy spy(&bar, &InputBar::sendRequested);
    bar.setBackendState(ConnectionState::Connected);

    // Enter 发送（原单行输入语义不回归）。
    editor->setPlainText(QStringLiteral("回车发送"));
    QTest::keyClick(editor, Qt::Key_Return);
    QCOMPARE(spy.count(), 1);
    QCOMPARE(spy.takeFirst().at(0).toString(), QStringLiteral("回车发送"));

    // Shift+Enter 插入换行、不发送。
    editor->setPlainText(QStringLiteral("第一行"));
    QTest::keyClick(editor, Qt::Key_Return, Qt::ShiftModifier);
    QCOMPARE(spy.count(), 0);
    QVERIFY(editor->toPlainText().contains(QStringLiteral("\n")));
}

void TestInputBar::attachButtonEmits()
{
    InputBar bar;
    QSignalSpy spy(&bar, &InputBar::attachRequested);
    QPushButton *attach =
        bar.findChild<QPushButton *>(QStringLiteral("attachButton"));
    QVERIFY(attach != nullptr);
    bar.setBackendState(ConnectionState::Connected);
    QTest::mouseClick(attach, Qt::LeftButton);
    QCOMPARE(spy.count(), 1);
}

void TestInputBar::setInputTextPrefills()
{
    InputBar bar;
    QPlainTextEdit *editor =
        bar.findChild<QPlainTextEdit *>(QStringLiteral("inputEdit"));
    bar.setInputText(QStringLiteral("预填内容"));
    QCOMPARE(editor->toPlainText(), QStringLiteral("预填内容"));
}

void TestInputBar::controlsHaveAccessibleNames()
{
    InputBar bar;
    QPlainTextEdit *editor =
        bar.findChild<QPlainTextEdit *>(QStringLiteral("inputEdit"));
    QPushButton *attach =
        bar.findChild<QPushButton *>(QStringLiteral("attachButton"));
    QPushButton *send =
        bar.findChild<QPushButton *>(QStringLiteral("sendButton"));
    QPushButton *memoryChip =
        bar.findChild<QPushButton *>(QStringLiteral("memoryChip"));
    QVERIFY(editor != nullptr);
    QVERIFY(attach != nullptr);
    QVERIFY(send != nullptr);
    QVERIFY(memoryChip != nullptr);
    QVERIFY(!editor->accessibleName().isEmpty());
    QVERIFY(!attach->accessibleName().isEmpty());
    QVERIFY(!send->accessibleName().isEmpty());
    QVERIFY(!memoryChip->accessibleName().isEmpty());
}

void TestInputBar::chipsEmitSignals()
{
    InputBar bar;
    QSignalSpy memorySpy(&bar, &InputBar::memoryPanelRequested);
    QSignalSpy settingsSpy(&bar, &InputBar::settingsRequested);
    QSignalSpy syncSpy(&bar, &InputBar::syncPanelRequested);

    bar.findChild<QPushButton *>(QStringLiteral("memoryChip"))->click();
    bar.findChild<QPushButton *>(QStringLiteral("settingsChip"))->click();
    bar.findChild<QPushButton *>(QStringLiteral("syncChip"))->click();
    QCOMPARE(memorySpy.count(), 1);
    QCOMPARE(settingsSpy.count(), 1);
    QCOMPARE(syncSpy.count(), 1);
}

void TestInputBar::moreMenuEmitsSignals()
{
    InputBar bar;
    QSignalSpy memorySpy(&bar, &InputBar::memoryPanelRequested);
    QSignalSpy settingsSpy(&bar, &InputBar::settingsRequested);
    QSignalSpy syncSpy(&bar, &InputBar::syncPanelRequested);
    QMenu *menu = bar.findChild<QMenu *>(QStringLiteral("moreMenu"));
    QVERIFY(menu != nullptr);

    for (QAction *action : menu->actions()) {
        if (action->text() == QStringLiteral("记忆面板")) {
            action->trigger();
        } else if (action->text() == QStringLiteral("设置")) {
            action->trigger();
        } else if (action->text() == QStringLiteral("同步面板")) {
            action->trigger();
        }
    }
    QCOMPARE(memorySpy.count(), 1);
    QCOMPARE(settingsSpy.count(), 1);
    QCOMPARE(syncSpy.count(), 1);
}

void TestInputBar::backendStateUpdatesBadgeAndAvailability()
{
    InputBar bar;
    QLabel *badge = bar.findChild<QLabel *>(QStringLiteral("inputStateBadge"));
    QPlainTextEdit *editor =
        bar.findChild<QPlainTextEdit *>(QStringLiteral("inputEdit"));
    QPushButton *importChip =
        bar.findChild<QPushButton *>(QStringLiteral("importChip"));
    QPushButton *memoryChip =
        bar.findChild<QPushButton *>(QStringLiteral("memoryChip"));
    QVERIFY(badge != nullptr);
    QVERIFY(editor != nullptr);
    QVERIFY(importChip != nullptr);
    QVERIFY(memoryChip != nullptr);

    bar.setBackendState(ConnectionState::Connected);
    QCOMPARE(badge->text(), QStringLiteral("● 在线"));
    QVERIFY(editor->isEnabled());
    QVERIFY(importChip->isEnabled());

    bar.setBackendState(ConnectionState::Disconnected);
    QCOMPARE(badge->text(), QStringLiteral("● 离线"));
    QVERIFY(!editor->isEnabled());
    QVERIFY(!importChip->isEnabled());
    QVERIFY(memoryChip->isEnabled());
}

void TestInputBar::chipsCollapseIntoMoreWhenNarrow()
{
    InputBar bar;
    bar.show();
    QVERIFY(QTest::qWaitForWindowExposed(&bar));

    const QList<QPushButton *> chips = {
        bar.findChild<QPushButton *>(QStringLiteral("memoryChip")),
        bar.findChild<QPushButton *>(QStringLiteral("settingsChip")),
        bar.findChild<QPushButton *>(QStringLiteral("importChip")),
        bar.findChild<QPushButton *>(QStringLiteral("syncChip")),
    };
    QPushButton *more =
        bar.findChild<QPushButton *>(QStringLiteral("moreChip"));
    QVERIFY(more != nullptr);

    bar.resize(560, 140);
    for (QPushButton *chip : chips) {
        QVERIFY(chip->isVisible());
    }
    QVERIFY(more->isVisible());

    bar.resize(220, 140);
    int hidden = 0;
    for (QPushButton *chip : chips) {
        if (!chip->isVisible()) {
            ++hidden;
        }
    }
    QVERIFY(hidden > 0);
    QVERIFY(more->isVisible());
}

QTEST_MAIN(TestInputBar)
#include "t_input_bar.moc"
