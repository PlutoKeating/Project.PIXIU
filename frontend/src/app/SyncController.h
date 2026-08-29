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

    // 发现局域网设备（GET /sync/discover；幂等，在途时忽略重复调用）。
    void discover();

    // 发起确认式配对请求（POST /sync/pair/request，targetId 为目标设备）。
    // 结果经 pairingResult 上抛（request_id/pin/expires_at）。
    void requestPairing(const QString &targetId);

    // 确认/拒绝一条配对请求（POST /sync/pair/confirm）。结果经 pairingResult
    // 上抛（status: accepted|rejected|expired）。
    void confirmPairing(const QString &requestId, bool accept);

    // 运行时开关更新（PUT /sync/settings）。结果经 settingsResult 上抛。
    void updateSettings(bool enabled, bool paused);

    // 立即同步：后端无 /sync/now 端点，复用 refresh()（syncStatus + peers）
    // 语义，结果仍经 syncStatusLoaded/peersLoaded 上抛（无独立结果信号）。
    void syncNow();

signals:
    void peersLoaded(const QJsonArray &peers);
    void syncStatusLoaded(const QJsonObject &status);
    void revoked(const QString &peerId);
    // 发现设备列表（GET /sync/discover → devices 数组）。
    void discoveredDevices(const QJsonArray &devices);
    // 配对请求发起/确认结果（request：request_id/pin/target_device_id/
    // expires_at；confirm：status accepted|rejected|expired）。
    void pairingResult(const QJsonObject &response);
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
    void handleDevicesResponse(const QJsonArray &devices);
    void handlePairRequestResponse(const QJsonObject &response);
    void handlePairConfirmResponse(const QJsonObject &response);
    void handleSettingsResponse(const QJsonObject &response);

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
