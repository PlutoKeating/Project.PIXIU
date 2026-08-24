#ifndef PIXIU_BACKEND_TRANSPORT_H
#define PIXIU_BACKEND_TRANSPORT_H

#include <QJsonArray>
#include <QJsonObject>
#include <QObject>
#include <QString>

#include "services/BackendTypes.h"

// 后端传输抽象接口：UI 层只依赖本接口与 BackendTypes，不感知具体协议。
//
// 当前实现为 HTTP transport（Phase 3.2）；D-Bus 后端契约落地后可作为第二实现。
class BackendTransport : public QObject
{
    Q_OBJECT

public:
    explicit BackendTransport(QObject *parent = nullptr);
    ~BackendTransport() override;

    // 建立连接（HTTP 下为健康探测）。幂等。
    virtual void connectToBackend() = 0;
    virtual void disconnectFromBackend() = 0;

    // REST 操作（实现异步发出请求，结果经信号返回）。
    // 提交查询并返回请求 ID（用于取消/过期响应判定）。
    virtual quint64 queryMemory(const QString &text, const QJsonObject &contextHint) = 0;
    virtual void writeMemory(const QJsonObject &payload) = 0;
    virtual void forget(const QString &command, bool confirm) = 0;
    virtual void listConflicts() = 0;
    virtual void preferenceHistory(const QString &preferenceId) = 0;
    // 偏好提取（POST /preference/extract，evidence_ids 由上层提供）。
    // 基类提供默认空实现，非 HTTP 传输/测试桩无需强制实现。
    virtual void extractPreferences(const QJsonObject &payload);
    // 偏好列表（GET /preferences?scope=）。默认空实现，理由同上。
    virtual void preferencesList(const QString &scope);
    // 证据详情（GET /evidence/{id}）。默认空实现，理由同上。
    virtual void evidenceDetail(const QString &evidenceId);
    // 配对令牌生成（POST /sync/token）。默认空实现，理由同上。
    virtual void createPairingToken(const QJsonObject &payload);
    virtual void promoteMemory(const QJsonObject &payload) = 0;
    virtual void pairDevice(const QJsonObject &payload) = 0;
    virtual void listPeers() = 0;
    virtual void syncStatus() = 0;
    virtual void revokePeer(const QString &peerId) = 0;

    // 当前连接状态。
    virtual ConnectionState connectionState() const = 0;
    // 后端基础地址（如 http://127.0.0.1:8765），供 WS/D-Bus 等通道派生端点。
    virtual QString baseUrl() const = 0;

signals:
    void connectionStateChanged(ConnectionState state);

    // 查询响应（/memory/query），携带请求 ID。
    void queryResult(quint64 requestId, const QJsonObject &atom);
    // 写入响应（/memory/write）。
    void writeAcknowledged(const QJsonObject &response);
    // 遗忘响应（/forget，confirm=false 为待确认、confirm=true 为已执行）。
    void forgetResult(const QJsonObject &response);
    // 冲突审计列表（GET /conflicts → {"conflicts": [...]}）。
    void conflictsResult(const QJsonArray &conflicts);
    // 偏好历史（GET /preference/{id}/history）。
    void preferenceHistoryResult(const QJsonObject &response);
    // 偏好提取响应（POST /preference/extract）。
    void preferenceExtractResult(const QJsonObject &response);
    // 偏好列表（GET /preferences → {"preferences": [...]}）。
    void preferencesListResult(const QJsonArray &preferences);
    // 证据详情（GET /evidence/{id}）。
    void evidenceDetailResult(const QJsonObject &evidence);
    // 配对令牌（POST /sync/token → {"token", "method", "ttl_seconds"}）。
    void pairingTokenResult(const QJsonObject &response);
    // 记忆流转（POST /memory/flow/promote）。
    void promoteResult(const QJsonObject &response);
    // 设备配对（POST /sync/pair）。
    void pairResult(const QJsonObject &response);
    // 节点列表响应（GET /sync/peers）。携带完整响应体，便于上层区分契约
    // 成功态（{"peers":[...]}）与后端占位态（{"status":"not_implemented"}）。
    void peersResult(const QJsonObject &response);
    // 同步状态（GET /sync/status）。
    void syncStatusResult(const QJsonObject &status);
    // 解绑（POST /sync/peers/{id}/revoke）。
    void revokeResult(const QJsonObject &response);

    // 通用错误；code 取 API 错误码或 NETWORK_ERROR / TIMEOUT。
    void errorOccurred(const QString &code, const QString &message, const QString &requestId);
    // 查询请求失败（携带请求 ID，供取消/过期判定）。
    void queryFailed(quint64 requestId, const QString &code, const QString &message);

    // WebSocket 业务事件（Phase 4 接入）。
    void backendEvent(const QJsonObject &event);
};

#endif // PIXIU_BACKEND_TRANSPORT_H
