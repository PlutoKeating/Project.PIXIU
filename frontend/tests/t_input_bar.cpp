#include <QLineEdit>
#include <QPushButton>
#include <QSignalSpy>
#include <QTest>

#include "widgets/InputBar.h"

// InputBar 交互测试：发送/回车/附件/空文本/输入恢复。
class TestInputBar : public QObject
{
    Q_OBJECT

private slots:
    void emptyTextDoesNotEmit();
    void typingEnablesSendButton();
    void sendEmitsAndClears();
    void returnKeyEmits();
    void attachButtonEmits();
    void setInputTextPrefills();
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
    QLineEdit *lineEdit =
        bar.findChild<QLineEdit *>(QStringLiteral("lineEdit"));
    QPushButton *send =
        bar.findChild<QPushButton *>(QStringLiteral("sendButton"));

    lineEdit->setText(QStringLiteral("  "));
    QVERIFY(!send->isEnabled());
    lineEdit->setText(QStringLiteral("问题"));
    QVERIFY(send->isEnabled());
    lineEdit->clear();
    QVERIFY(!send->isEnabled());
}

void TestInputBar::sendEmitsAndClears()
{
    InputBar bar;
    QLineEdit *lineEdit =
        bar.findChild<QLineEdit *>(QStringLiteral("lineEdit"));
    QPushButton *send =
        bar.findChild<QPushButton *>(QStringLiteral("sendButton"));
    QSignalSpy spy(&bar, &InputBar::sendRequested);

    lineEdit->setText(QStringLiteral("  发送内容  "));
    QTest::mouseClick(send, Qt::LeftButton);

    QCOMPARE(spy.count(), 1);
    QCOMPARE(spy.takeFirst().at(0).toString(), QStringLiteral("发送内容"));
    QVERIFY(lineEdit->text().isEmpty());
}

void TestInputBar::returnKeyEmits()
{
    InputBar bar;
    QLineEdit *lineEdit =
        bar.findChild<QLineEdit *>(QStringLiteral("lineEdit"));
    QSignalSpy spy(&bar, &InputBar::sendRequested);

    lineEdit->setText(QStringLiteral("回车发送"));
    QTest::keyClick(lineEdit, Qt::Key_Return);

    QCOMPARE(spy.count(), 1);
    QCOMPARE(spy.takeFirst().at(0).toString(), QStringLiteral("回车发送"));
}

void TestInputBar::attachButtonEmits()
{
    InputBar bar;
    QSignalSpy spy(&bar, &InputBar::attachRequested);
    QPushButton *attach =
        bar.findChild<QPushButton *>(QStringLiteral("attachButton"));
    QVERIFY(attach != nullptr);
    QTest::mouseClick(attach, Qt::LeftButton);
    QCOMPARE(spy.count(), 1);
}

void TestInputBar::setInputTextPrefills()
{
    InputBar bar;
    QLineEdit *lineEdit =
        bar.findChild<QLineEdit *>(QStringLiteral("lineEdit"));
    bar.setInputText(QStringLiteral("预填内容"));
    QCOMPARE(lineEdit->text(), QStringLiteral("预填内容"));
}

QTEST_MAIN(TestInputBar)
#include "t_input_bar.moc"
