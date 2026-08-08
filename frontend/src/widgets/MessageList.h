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

    // 查询失败提示行：红字详情 + 重试按钮；点击重试时以 retryRequested
    // 携带原始查询文本上抛（UI 不直接调用 controller）。
    void appendQueryError(const QString &retryText, const QString &detail);

signals:
    // 点击证据卡（回溯原文）。
    void evidenceClicked(const QString &evidenceId);
    // 点击失败提示行的“重试”按钮（携带原始查询文本）。
    void retryRequested(const QString &text);

private:
    QWidget *createUserBubble(const ChatMessage &message) const;
    QWidget *createAssistantBubble(const ChatMessage &message) const;
    QWidget *createSystemBubble(const ChatMessage &message) const;
    void appendRow(QWidget *content, Qt::Alignment alignment);

    bool m_thinking = false;
};

#endif // PIXIU_MESSAGE_LIST_H
