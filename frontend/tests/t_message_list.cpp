#include <QLabel>
#include <QPushButton>
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
    void longSystemMessageWrapsWithinBubbleWidth();
    void evidenceCardWidthMatchesBubble();
    void thinkingPlaceholderIsReplacedByNextMessage();
    void clearMessagesEmptiesList();
    void evidenceClickIsForwarded();
    void queryErrorShowsDetailAndRetryEmitsRequest();
    void emptyResultShowsImportButtonAndEmitsRequest();
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
    QWidget *content = list.itemWidget(list.item(0));
    QVERIFY(content != nullptr);
    // 系统提示行内容即 systemHint 标签本身（appendRow 直接放入）。
    QLabel *hint = qobject_cast<QLabel *>(content);
    QVERIFY(hint != nullptr);
    QCOMPARE(hint->objectName(), QStringLiteral("systemHint"));
    QVERIFY(hint->wordWrap());
}

void TestMessageList::longSystemMessageWrapsWithinBubbleWidth()
{
    MessageList list;
    list.appendMessage(makeMessage(
        MessageRole::System,
        QStringLiteral("Backend service is offline. Please start the PIXIU "
                       "backend service and retry.")));
    QCOMPARE(list.count(), 1);

    QWidget *content = list.itemWidget(list.item(0));
    QVERIFY(content != nullptr);
    QLabel *hint = qobject_cast<QLabel *>(content);
    QVERIFY(hint != nullptr);
    QCOMPARE(hint->objectName(), QStringLiteral("systemHint"));
    QVERIFY(hint->wordWrap());
    // 系统提示与答案气泡同宽（300px），长文案换行而非撑宽被裁剪。
    QVERIFY(hint->maximumWidth() > 0);
    QVERIFY(hint->maximumWidth() < 400);
}

void TestMessageList::evidenceCardWidthMatchesBubble()
{
    MessageList list;
    ChatMessage message =
        makeMessage(MessageRole::Assistant, QStringLiteral("答案"));
    message.evidenceId = QStringLiteral("evd_01HABCDEFGHIJKLMNOPQRSTUVWXYZ");
    message.confidence = 0.93;
    message.latencyMs = 210;
    list.appendMessage(message);

    QWidget *content = list.itemWidget(list.item(0));
    QVERIFY(content != nullptr);
    EvidenceCard *card = content->findChild<EvidenceCard *>();
    QVERIFY(card != nullptr);
    // 证据卡与气泡同宽，长元信息在卡内换行而非撑宽卡片。
    QVERIFY(card->maximumWidth() > 0);
    QVERIFY(card->maximumWidth() < 400);
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

void TestMessageList::queryErrorShowsDetailAndRetryEmitsRequest()
{
    MessageList list;
    QSignalSpy spy(&list, &MessageList::retryRequested);

    list.appendQueryError(QStringLiteral("燃气费是多少"),
                          QStringLiteral("查询失败（timeout）：连接超时\n输入已保留。"));
    QCOMPARE(list.count(), 1);

    QWidget *content = list.itemWidget(list.item(0));
    QVERIFY(content != nullptr);

    QLabel *hint = content->findChild<QLabel *>(QStringLiteral("queryErrorHint"));
    QVERIFY(hint != nullptr);
    QVERIFY(hint->text().contains(QStringLiteral("timeout")));

    QPushButton *retry = content->findChild<QPushButton *>(QStringLiteral("retryButton"));
    QVERIFY(retry != nullptr);
    QCOMPARE(retry->text(), QStringLiteral("重试"));

    QTest::mouseClick(retry, Qt::LeftButton);
    QCOMPARE(spy.count(), 1);
    QCOMPARE(spy.takeFirst().at(0).toString(), QStringLiteral("燃气费是多少"));
}

void TestMessageList::emptyResultShowsImportButtonAndEmitsRequest()
{
    MessageList list;
    QSignalSpy spy(&list, &MessageList::importKnowledgeRequested);

    list.appendEmptyResult(QStringLiteral("未找到相关记忆，换个说法试试。"));
    QCOMPARE(list.count(), 1);

    QWidget *content = list.itemWidget(list.item(0));
    QVERIFY(content != nullptr);

    QLabel *hint = content->findChild<QLabel *>(QStringLiteral("emptyHint"));
    QVERIFY(hint != nullptr);
    QVERIFY(hint->text().contains(QStringLiteral("未找到相关记忆")));

    QPushButton *import =
        content->findChild<QPushButton *>(QStringLiteral("importKnowledgeButton"));
    QVERIFY(import != nullptr);
    QCOMPARE(import->text(), QStringLiteral("录入知识"));

    QTest::mouseClick(import, Qt::LeftButton);
    QCOMPARE(spy.count(), 1);
}

QTEST_MAIN(TestMessageList)
#include "t_message_list.moc"
