#ifndef PIXIU_WEBSOCKET_CLIENT_H
#define PIXIU_WEBSOCKET_CLIENT_H

#include <QJsonObject>
#include <QObject>
#include <QString>
#include <QTimer>

#include "services/BackendTypes.h"

class QWebSocket;

// WebSocket 事件客户端：订阅后端 /events 推送。
//
// 约定（对齐 frontend/docs/DEVELOPMENT_PLAN.md §3.2）：
//   - connected / ping 等控制事件只更新连接状态，不向 UI 抛业务事件；
//   - 依据顶层 "event" 字段分发，data 缺失/类型错误时脱敏记录并安全忽略；
//   - 未知事件保持前向兼容：仅记录并忽略，不崩溃、不断开、不弹错；
//   - 断线后指数退避重连（1s→2s→4s→…→30s 封顶），成功连接后复位。
class WebSocketClient : public QObject
{
    Q_OBJECT

public:
    explicit WebSocketClient(QObject *parent = nullptr);
    ~WebSocketClient() override;

    // 以后端 HTTP 基址（如 http://127.0.0.1:8765）配置 WS 地址。
    void setBackendUrl(const QString &baseUrl);

    void connectToBackend();
    void disconnectFromBackend();
    bool isConnected() const;

signals:
    void connectionStateChanged(ConnectionState state);
    // 业务事件（不含控制事件）：{"event": "...", "data": {...}}
    void eventReceived(const QJsonObject &event);

private:
    void scheduleReconnect();
    void resetReconnect();
    void onTextMessageReceived(const QString &message);

    QWebSocket *m_socket = nullptr;
    QTimer m_reconnectTimer;
    QString m_wsUrl;
    int m_reconnectAttempts = 0;
    bool m_stopped = true;
};

#endif // PIXIU_WEBSOCKET_CLIENT_H
