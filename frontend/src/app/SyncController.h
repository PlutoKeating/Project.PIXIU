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
//   - 兼容旧后端的 {"status":"not_implemented"}（HTTP 200）响应并如实上报
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

    // 发现局域网设备（GET /sync/discover；幂等，在途时忽略重复调用）。
    void discover();

    // 发起确认式配对请求（POST /sync/pair/request，targetId 为目标设备）。
    // 结果经 pairRequestResult 上抛（request_id/pin/expires_at）。
    void requestPairing(const QString &targetId);

    // 确认/拒绝一条配对请求（POST /sync/pair/confirm）。结果经
    // pairConfirmResult 上抛（status: accepted|rejected|expired）。
    void confirmPairing(const QString &requestId, bool accept);

    // 运行时开关更新（PUT /sync/settings）。结果经 settingsResult 上抛。
    void updateSettings(bool enabled, bool paused);

signals:
    void peersLoaded(const QJsonArray &peers);
    void syncStatusLoaded(const QJsonObject &status);
    void revoked(const QString &peerId);
    // 发现设备列表（GET /sync/discover → devices 数组）。
    void discoveredDevices(const QJsonArray &devices);
    // 配对请求发起结果（request_id/pin/target_device_id/expires_at）。
    void pairRequestResult(const QJsonObject &response);
    // 配对确认结果（status: accepted|rejected|expired）。
    void pairConfirmResult(const QJsonObject &response);
    // 运行时开关更新结果（enabled/paused）。
    void settingsResult(const QJsonObject &response);
    // feature ∈ {"peers","sync_status","revoke","discover","pair_request",
    // "pair_confirm","settings"}。
    void notImplemented(const QString &feature);
    void failed(const QString &code, const QString &message);

private:
    void handlePeersResponse(const QJsonObject &response);
    void handleSyncStatusResponse(const QJsonObject &response);
    void handleRevokeResponse(const QJsonObject &response);
    void handleDevicesResponse(const QJsonObject &response);
    void handlePairRequestResponse(const QJsonObject &response);
    void handlePairConfirmResponse(const QJsonObject &response);
    void handleSettingsResponse(const QJsonObject &response);
    // 通用错误到达时清空全部在途标记（全量清理语义，见 errorOccurred 处理）。
    void clearAllPending();

    BackendTransport *m_transport = nullptr;
    bool m_peersPending = false;
    bool m_statusPending = false;
    bool m_revokePending = false;
    bool m_discoverPending = false;
    bool m_pairRequestPending = false;
    bool m_pairConfirmPending = false;
    bool m_settingsPending = false;
    QString m_revokePeerId;
};

#endif // PIXIU_SYNC_CONTROLLER_H
