#ifndef PIXIU_CHAT_MESSAGE_H
#define PIXIU_CHAT_MESSAGE_H

#include <QString>

// 对话消息模型（纯数据，非 QObject）。
enum class MessageRole
{
    User,      // 用户提问（右对齐蓝色气泡）
    Assistant, // 系统回答（左对齐浅色气泡 + 证据信息）
    System     // 系统提示（居中灰色文本）
};

struct ChatMessage
{
    MessageRole role = MessageRole::User;
    QString text;
    qint64 timestamp = 0;     // Unix 秒
    QString evidenceId;       // 关联证据 ID（可选）
    double confidence = 0.0;  // 答案置信度（可选）
    int latencyMs = 0;        // 检索延迟（可选）
};

#endif // PIXIU_CHAT_MESSAGE_H
