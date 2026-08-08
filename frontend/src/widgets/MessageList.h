#ifndef PIXIU_MESSAGE_LIST_H
#define PIXIU_MESSAGE_LIST_H

#include <QListWidget>

#include "models/ChatMessage.h"

// 对话气泡列表：用户气泡右对齐、回答气泡左对齐、系统提示居中。
class MessageList : public QListWidget
{
    Q_OBJECT

public:
    explicit MessageList(QWidget *parent = nullptr);

    void appendMessage(const ChatMessage &message);
    void clearMessages();

    // 答案加载占位（骨架屏）。
    void setThinking(bool thinking);

signals:
    // 点击证据卡（回溯原文）。
    void evidenceClicked(const QString &evidenceId);

private:
    QWidget *createUserBubble(const ChatMessage &message) const;
    QWidget *createAssistantBubble(const ChatMessage &message) const;
    QWidget *createSystemBubble(const ChatMessage &message) const;
    void appendRow(QWidget *content, Qt::Alignment alignment);

    bool m_thinking = false;
};

#endif // PIXIU_MESSAGE_LIST_H
