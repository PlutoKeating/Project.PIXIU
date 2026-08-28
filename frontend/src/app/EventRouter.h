#ifndef PIXIU_EVENT_ROUTER_H
#define PIXIU_EVENT_ROUTER_H

#include <QJsonArray>
#include <QJsonObject>
#include <QObject>
#include <QString>

// WebSocket 业务事件路由器：把 WS 事件帧解析为语义信号，UI 层只订阅语义。
//
// 覆盖 docs/API.md §4 定义的五类业务事件（memory_ready / conflict_detected /
// forget_confirmation / sync_event / capture_event）。未知事件与 data 缺失/
// 类型错误的帧安全忽略：不崩溃、不断开连接、不向 UI 抛原始 payload。
// WebSocketClient 已过滤未知事件，本类做应用层二次防御。
class EventRouter : public QObject
{
    Q_OBJECT

public:
    explicit EventRouter(QObject *parent = nullptr);

    // 分发一条业务事件帧（{"event": "...", "data": {...}}）。
    void handleEvent(const QJsonObject &event);

signals:
    void memoryReady(const QJsonObject &data);
    void conflictDetected(const QString &knowledgeTitle,
                          const QString &field,
                          const QString &oldValue,
                          const QString &newValue);
    void forgetConfirmationReady(const QString &command,
                                 const QJsonArray &targets,
                                 const QJsonObject &cascade,
                                 qint64 expiresAt);
    void syncEvent(const QJsonObject &data);
    // 监控捕获事件（docs/API.md §4.5）：信号只带契约保证存在的
    // source / status / summary / ts 四字段；evidence_id / knowledge_id 由
    // A-3 经 monitorLogResult 补全，本信号不展开。
    void captureEvent(const QString &source,
                      const QString &status,
                      const QString &summary,
                      qint64 ts);
};

#endif // PIXIU_EVENT_ROUTER_H
