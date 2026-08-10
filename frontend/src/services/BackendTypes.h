#ifndef PIXIU_BACKEND_TYPES_H
#define PIXIU_BACKEND_TYPES_H

#include <QJsonArray>
#include <QJsonObject>
#include <QString>
#include <QStringList>

// 后端连接状态模型。
enum class ConnectionState
{
    Disconnected, // 未连接
    Connecting,   // 正在探测
    Connected,    // 可用
    Error         // 探测失败/异常
};

// 后端错误（对齐 docs/API.md 错误码）。
struct BackendError
{
    QString code;      // INVALID_REQUEST / NOT_FOUND / NETWORK_ERROR / ...
    QString message;
    QString requestId;

    bool isNull() const { return code.isEmpty() && message.isEmpty(); }
};

// 从错误响应体解析（容忍未知字段）。
inline BackendError parseBackendError(const QJsonObject &body)
{
    BackendError error;
    error.code = body.value(QStringLiteral("error")).toString();
    error.message = body.value(QStringLiteral("message")).toString();
    error.requestId = body.value(QStringLiteral("request_id")).toString();

    // 后端实际错误形状：FastAPI HTTPException 返回 {"detail": "..."}，
    // Pydantic 校验失败返回 {"detail": [{"loc","msg","type",...}, ...]}。
    // 两者都对齐到 API 错误码，避免 UI 只显示空白 "HTTP_4xx"。
    if (error.code.isEmpty() && body.contains(QStringLiteral("detail"))) {
        const QJsonValue detail = body.value(QStringLiteral("detail"));
        if (detail.isString()) {
            error.code = detail.toString();
            error.message = detail.toString();
        } else if (detail.isArray()) {
            error.code = QStringLiteral("INVALID_REQUEST");
            QStringList messages;
            const QJsonArray items = detail.toArray();
            for (const QJsonValue &item : items) {
                const QString msg =
                    item.toObject().value(QStringLiteral("msg")).toString();
                if (!msg.isEmpty()) {
                    messages << msg;
                }
            }
            error.message = messages.isEmpty()
                                ? QStringLiteral("请求参数校验失败")
                                : messages.join(QStringLiteral("; "));
        }
    }
    return error;
}

inline QString connectionStateName(ConnectionState state)
{
    switch (state) {
    case ConnectionState::Disconnected:
        return QStringLiteral("disconnected");
    case ConnectionState::Connecting:
        return QStringLiteral("connecting");
    case ConnectionState::Connected:
        return QStringLiteral("connected");
    case ConnectionState::Error:
        return QStringLiteral("error");
    }
    return QStringLiteral("unknown");
}

#endif // PIXIU_BACKEND_TYPES_H
