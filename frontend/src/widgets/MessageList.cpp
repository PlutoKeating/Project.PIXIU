#include "widgets/MessageList.h"

#include <QDateTime>
#include <QHBoxLayout>
#include <QLabel>
#include <QVBoxLayout>

#include "widgets/EvidenceCard.h"

namespace {
constexpr int kBubbleMaxWidth = 300;

QString formatTimestamp(qint64 ts)
{
    return QDateTime::fromSecsSinceEpoch(ts).toString(QStringLiteral("HH:mm"));
}

QLabel *makeBubbleLabel(const QString &text, const QString &objectName, int maxWidth)
{
    QLabel *label = new QLabel(text);
    label->setWordWrap(true);
    label->setMaximumWidth(maxWidth);
    label->setTextFormat(Qt::PlainText);
    label->setObjectName(objectName);
    return label;
}
}

MessageList::MessageList(QWidget *parent)
    : QListWidget(parent)
{
    setFrameShape(QFrame::NoFrame);
    setHorizontalScrollBarPolicy(Qt::ScrollBarAlwaysOff);
    setSelectionMode(QAbstractItemView::NoSelection);
    setFocusPolicy(Qt::NoFocus);
    setObjectName(QStringLiteral("messageList"));
}

void MessageList::appendMessage(const ChatMessage &message)
{
    if (m_thinking) {
        clearMessages();
    }

    switch (message.role) {
    case MessageRole::User:
        appendRow(createUserBubble(message), Qt::AlignRight);
        break;
    case MessageRole::Assistant:
        appendRow(createAssistantBubble(message), Qt::AlignLeft);
        break;
    case MessageRole::System:
        appendRow(createSystemBubble(message), Qt::AlignCenter);
        break;
    }
    scrollToBottom();
}

void MessageList::clearMessages()
{
    m_thinking = false;
    QListWidget::clear();
}

void MessageList::setThinking(bool thinking)
{
    m_thinking = thinking;
    if (thinking) {
        ChatMessage hint;
        hint.role = MessageRole::System;
        hint.text = tr("思考中…");
        hint.timestamp = QDateTime::currentSecsSinceEpoch();
        appendRow(createSystemBubble(hint), Qt::AlignCenter);
        scrollToBottom();
    }
}

QWidget *MessageList::createUserBubble(const ChatMessage &message) const
{
    QLabel *bubble =
        makeBubbleLabel(message.text, QStringLiteral("userBubble"), kBubbleMaxWidth);

    QWidget *container = new QWidget();
    QHBoxLayout *layout = new QHBoxLayout(container);
    layout->setContentsMargins(0, 0, 0, 0);
    layout->addStretch(1);
    layout->addWidget(bubble);
    return container;
}

QWidget *MessageList::createAssistantBubble(const ChatMessage &message) const
{
    QLabel *bubble =
        makeBubbleLabel(message.text, QStringLiteral("assistantBubble"), kBubbleMaxWidth);

    QWidget *container = new QWidget();
    QVBoxLayout *layout = new QVBoxLayout(container);
    layout->setContentsMargins(0, 0, 0, 0);
    layout->setSpacing(2);
    layout->addWidget(bubble);

    // 证据卡占位行（置信度 + 延迟 + 证据 ID）。
    if (message.confidence > 0.0 || !message.evidenceId.isEmpty()) {
        QString meta = tr("置信度 %1 · 延迟 %2ms")
                           .arg(QString::number(message.confidence, 'f', 2))
                           .arg(message.latencyMs);
        QLabel *metaLabel = new QLabel(meta);
        metaLabel->setObjectName(QStringLiteral("assistantMeta"));
        layout->addWidget(metaLabel);
    }
    if (!message.evidenceId.isEmpty()) {
        EvidenceCard *card =
            new EvidenceCard(message.evidenceId, message.confidence, message.latencyMs);
        connect(card, &EvidenceCard::evidenceClicked,
                this, &MessageList::evidenceClicked);
        layout->addWidget(card);
    }
    return container;
}

QWidget *MessageList::createSystemBubble(const ChatMessage &message) const
{
    QLabel *label = new QLabel(message.text);
    label->setObjectName(QStringLiteral("systemHint"));
    label->setAlignment(Qt::AlignCenter);
    return label;
}

void MessageList::appendRow(QWidget *content, Qt::Alignment alignment)
{
    QListWidgetItem *item = new QListWidgetItem();
    item->setFlags(Qt::ItemIsEnabled);
    item->setSizeHint(content->sizeHint());
    addItem(item);
    setItemWidget(item, content);
}
