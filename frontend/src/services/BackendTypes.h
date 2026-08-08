#ifndef PIXIU_BACKEND_TYPES_H
#define PIXIU_BACKEND_TYPES_H

#include <QJsonObject>
#include <QString>

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
