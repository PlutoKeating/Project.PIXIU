#ifndef PIXIU_SYNC_CONTROLLER_H
#define PIXIU_SYNC_CONTROLLER_H

#include <QJsonArray>
#include <QJsonObject>
#include <QObject>
#include <QString>

class BackendTransport;

// 同步管理控制器：封装 /sync/peers、/sync/status 与 /sync/peers/{id}/revoke
// 的请求与结果上抛（Phase 6 节点列表 / 同步状态 / 解绑）。
//
// 契约语义（docs/API.md §3.9-3.11）：
//   - 后端占位实现返回 {"status":"not_implemented"}（HTTP 200）时，如实上报
//     notImplemented(feature)，不把空数组/空对象当作成功；
//   - 解绑仅在契约成功态 status=revoked 时上报 revoked；
//   - 网络/HTTP/API 错误走 failed，不伪造成功。
class SyncController : public QObject
{
    Q_OBJECT

public:
    explicit SyncController(BackendTransport *transport, QObject *parent = nullptr);

    // 刷新节点列表与同步状态（幂等；对应在途请求未返回时忽略重复调用）。
    void refresh();

    // 解绑设备（危险操作，UI 二次确认后调用）。
    void revokePeer(const QString &peerId);

signals:
    void peersLoaded(const QJsonArray &peers);
    void syncStatusLoaded(const QJsonObject &status);
    void revoked(const QString &peerId);
    // feature ∈ {"peers","sync_status","revoke"}。
    void notImplemented(const QString &feature);
    void failed(const QString &code, const QString &message);

private:
    void handlePeersResponse(const QJsonObject &response);
    void handleSyncStatusResponse(const QJsonObject &response);
    void handleRevokeResponse(const QJsonObject &response);

    BackendTransport *m_transport = nullptr;
    bool m_peersPending = false;
    bool m_statusPending = false;
    bool m_revokePending = false;
    QString m_revokePeerId;
};

#endif // PIXIU_SYNC_CONTROLLER_H
