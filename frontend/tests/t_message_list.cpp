#include <QLabel>
#include <QSignalSpy>
#include <QTest>

#include "widgets/EvidenceCard.h"
#include "widgets/MessageList.h"

// MessageList 气泡流测试：三种角色、思考占位、证据卡点击。
class TestMessageList : public QObject
{
    Q_OBJECT

private slots:
    void appendUserAddsBubble();
    void appendAssistantAddsEvidenceCard();
    void appendSystemAddsCenteredText();
    void thinkingPlaceholderIsReplacedByNextMessage();
    void clearMessagesEmptiesList();
    void evidenceClickIsForwarded();
};

static ChatMessage makeMessage(MessageRole role, const QString &text)
{
    ChatMessage message;
    message.role = role;
    message.text = text;
    message.timestamp = 1786164000;
    return message;
}

void TestMessageList::appendUserAddsBubble()
{
    MessageList list;
    list.appendMessage(makeMessage(MessageRole::User, QStringLiteral("你好")));
    QCOMPARE(list.count(), 1);
    QWidget *content = list.itemWidget(list.item(0));
    QVERIFY(content != nullptr);
    QVERIFY(!content->findChildren<QLabel *>().isEmpty());
}

void TestMessageList::appendAssistantAddsEvidenceCard()
{
    MessageList list;
    ChatMessage message =
        makeMessage(MessageRole::Assistant, QStringLiteral("434.50 元"));
    message.evidenceId = QStringLiteral("evd_01H");
    message.confidence = 0.93;
    message.latencyMs = 210;
    list.appendMessage(message);

    QCOMPARE(list.count(), 1);
    QWidget *content = list.itemWidget(list.item(0));
    QVERIFY(content->findChild<EvidenceCard *>() != nullptr);
}

void TestMessageList::appendSystemAddsCenteredText()
{
    MessageList list;
    list.appendMessage(makeMessage(MessageRole::System, QStringLiteral("后端未连接")));
    QCOMPARE(list.count(), 1);
}

void TestMessageList::thinkingPlaceholderIsReplacedByNextMessage()
{
    MessageList list;
    list.setThinking(true);
    QCOMPARE(list.count(), 1);

    // 新消息到达时替换思考占位，而不是追加。
    list.appendMessage(makeMessage(MessageRole::User, QStringLiteral("追问")));
    QCOMPARE(list.count(), 1);
}

void TestMessageList::clearMessagesEmptiesList()
{
    MessageList list;
    list.appendMessage(makeMessage(MessageRole::User, QStringLiteral("a")));
    list.appendMessage(makeMessage(MessageRole::Assistant, QStringLiteral("b")));
    list.clearMessages();
    QCOMPARE(list.count(), 0);
}

void TestMessageList::evidenceClickIsForwarded()
{
    MessageList list;
    ChatMessage message =
        makeMessage(MessageRole::Assistant, QStringLiteral("答案"));
    message.evidenceId = QStringLiteral("evd_42");
    message.confidence = 0.9;
    list.appendMessage(message);

    QWidget *content = list.itemWidget(list.item(0));
    EvidenceCard *card = content->findChild<EvidenceCard *>();
    QVERIFY(card != nullptr);

    QSignalSpy spy(&list, &MessageList::evidenceClicked);
    QTest::mouseClick(card, Qt::LeftButton);
    QCOMPARE(spy.count(), 1);
    QCOMPARE(spy.takeFirst().at(0).toString(), QStringLiteral("evd_42"));
}

QTEST_MAIN(TestMessageList)
#include "t_message_list.moc"
