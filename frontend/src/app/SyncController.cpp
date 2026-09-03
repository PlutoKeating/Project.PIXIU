#include "app/SyncController.h"

#include <QLoggingCategory>

#include "services/BackendTransport.h"

Q_LOGGING_CATEGORY(lcSync, "pixiu.sync")

SyncController::SyncController(BackendTransport *transport, QObject *parent)
    : QObject(parent)
    , m_transport(transport)
{
    connect(m_transport, &BackendTransport::peersResult,
            this, &SyncController::handlePeersResponse);
    connect(m_transport, &BackendTransport::syncStatusResult,
            this, &SyncController::handleSyncStatusResponse);
    connect(m_transport, &BackendTransport::revokeResult,
            this, &SyncController::handleRevokeResponse);
    connect(m_transport, &BackendTransport::devicesLoaded,
            this, &SyncController::handleDevicesResponse);
    connect(m_transport, &BackendTransport::pairRequestResult,
            this, &SyncController::handlePairRequestResponse);
    connect(m_transport, &BackendTransport::pairConfirmResult,
            this, &SyncController::handlePairConfirmResponse);
    connect(m_transport, &BackendTransport::settingsResult,
            this, &SyncController::handleSettingsResponse);
    connect(m_transport, &BackendTransport::errorOccurred, this,
            [this](const QString &code, const QString &message, const QString &) {
                // 通用错误通道：仅处理同步管理相关的在途请求，避免误吞
                // 配对/写入/冲突等其他端点的错误。
                if (!m_peersPending && !m_statusPending && !m_revokePending
                    && !m_discoverPending && !m_pairRequestPending
                    && !m_pairConfirmPending && !m_settingsPending) {
                    return;
                }
                // 全量清理语义：任一同步管理流程失败即清空全部在途标记，
                // 避免残留 pending 卡死后续请求。代价是其它并发在途流程
                // （如 discover 与 settings 同时进行）的成功响应随后会被
                // 各自的 stale 检查丢弃——SN-6 UI 必须序列化 discover/
                // settings 等交互，不做跨流程并发，本控制器因此无需按
                // 流程细分清理。
                clearAllPending();
                emit failed(code, message);
            });
}

void SyncController::clearAllPending()
{
    m_peersPending = false;
    m_statusPending = false;
    m_revokePending = false;
    m_discoverPending = false;
    m_pairRequestPending = false;
    m_pairConfirmPending = false;
    m_settingsPending = false;
    m_revokePeerId.clear();
}

void SyncController::refresh()
{
    if (!m_peersPending) {
        m_peersPending = true;
        qCInfo(lcSync) << "listing peers";
        m_transport->listPeers();
    }
    if (!m_statusPending) {
        m_statusPending = true;
        qCInfo(lcSync) << "loading sync status";
        m_transport->syncStatus();
    }
}

void SyncController::revokePeer(const QString &peerId)
{
    if (m_revokePending || peerId.trimmed().isEmpty()) {
        return;
    }
    m_revokePending = true;
    m_revokePeerId = peerId.trimmed();
    qCInfo(lcSync) << "revoking peer:" << m_revokePeerId;
    m_transport->revokePeer(m_revokePeerId);
}

void SyncController::discover()
{
    if (m_discoverPending) {
        return;
    }
    m_discoverPending = true;
    qCInfo(lcSync) << "discovering lan devices";
    m_transport->discoverDevices();
}

void SyncController::requestPairing(const QString &targetId)
{
    if (m_pairRequestPending || targetId.trimmed().isEmpty()) {
        return;
    }
    m_pairRequestPending = true;
    qCInfo(lcSync) << "requesting pairing with:" << targetId;
    m_transport->requestPairing(targetId.trimmed());
}

void SyncController::confirmPairing(const QString &requestId, bool accept)
{
    if (m_pairConfirmPending || requestId.trimmed().isEmpty()) {
        return;
    }
    m_pairConfirmPending = true;
    qCInfo(lcSync) << "confirming pairing request" << requestId
                   << (accept ? QStringLiteral("accept")
                              : QStringLiteral("reject"));
    m_transport->confirmPairing(requestId.trimmed(), accept);
}

void SyncController::updateSettings(bool enabled, bool paused)
{
    if (m_settingsPending) {
        return;
    }
    m_settingsPending = true;
    qCInfo(lcSync) << "updating sync settings: enabled" << enabled
                   << "paused" << paused;
    m_transport->updateSyncSettings(enabled, paused);
}

void SyncController::handlePeersResponse(const QJsonObject &response)
{
    if (!m_peersPending) {
        return; // 无在途请求，忽略过期响应
    }
    m_peersPending = false;

    if (response.value(QStringLiteral("status")).toString()
        == QStringLiteral("not_implemented")) {
        emit notImplemented(QStringLiteral("peers"));
        return;
    }
    if (!response.contains(QStringLiteral("peers"))) {
        emit failed(QStringLiteral("UNKNOWN_RESPONSE"),
                    tr("节点列表响应格式无法识别"));
        return;
    }
    emit peersLoaded(response.value(QStringLiteral("peers")).toArray());
}

void SyncController::handleSyncStatusResponse(const QJsonObject &response)
{
    if (!m_statusPending) {
        return; // 无在途请求，忽略过期响应
    }
    m_statusPending = false;

    if (response.value(QStringLiteral("status")).toString()
        == QStringLiteral("not_implemented")) {
        emit notImplemented(QStringLiteral("sync_status"));
        return;
    }
    if (response.isEmpty()) {
        emit failed(QStringLiteral("UNKNOWN_RESPONSE"),
                    tr("同步状态响应格式无法识别"));
        return;
    }
    emit syncStatusLoaded(response);
}

void SyncController::handleRevokeResponse(const QJsonObject &response)
{
    if (!m_revokePending) {
        return; // 无在途请求，忽略过期响应
    }
    const QString peerId = m_revokePeerId;
    m_revokePending = false;
    m_revokePeerId.clear();

    const QString status = response.value(QStringLiteral("status")).toString();
    if (status == QStringLiteral("revoked")) {
        qCInfo(lcSync) << "peer revoked:" << peerId;
        emit revoked(peerId);
        return;
    }
    if (status == QStringLiteral("not_implemented")) {
        emit notImplemented(QStringLiteral("revoke"));
        return;
    }
    if (status.isEmpty()) {
        emit failed(QStringLiteral("UNKNOWN_RESPONSE"),
                    tr("解绑响应格式无法识别"));
        return;
    }
    emit failed(status, tr("解绑失败：%1").arg(status));
}

void SyncController::handleDevicesResponse(const QJsonObject &response)
{
    if (!m_discoverPending) {
        return; // 无在途请求，忽略过期响应
    }
    m_discoverPending = false;
    emit discoveredDevices(response.value(QStringLiteral("devices")).toArray());
}

void SyncController::handlePairRequestResponse(const QJsonObject &response)
{
    if (!m_pairRequestPending) {
        return; // 无在途请求，忽略过期响应
    }
    m_pairRequestPending = false;

    if (response.value(QStringLiteral("status")).toString()
        == QStringLiteral("not_implemented")) {
        emit notImplemented(QStringLiteral("pair_request"));
        return;
    }
    if (response.isEmpty()) {
        emit failed(QStringLiteral("UNKNOWN_RESPONSE"),
                    tr("配对请求响应格式无法识别"));
        return;
    }
    emit pairRequestResult(response);
}

void SyncController::handlePairConfirmResponse(const QJsonObject &response)
{
    if (!m_pairConfirmPending) {
        return; // 无在途请求，忽略过期响应
    }
    m_pairConfirmPending = false;

    const QString status = response.value(QStringLiteral("status")).toString();
    if (status == QStringLiteral("not_implemented")) {
        emit notImplemented(QStringLiteral("pair_confirm"));
        return;
    }
    if (status.isEmpty()) {
        emit failed(QStringLiteral("UNKNOWN_RESPONSE"),
                    tr("配对确认响应格式无法识别"));
        return;
    }
    emit pairConfirmResult(response);
}

void SyncController::handleSettingsResponse(const QJsonObject &response)
{
    if (!m_settingsPending) {
        return; // 无在途请求，忽略过期响应
    }
    m_settingsPending = false;

    if (response.value(QStringLiteral("status")).toString()
        == QStringLiteral("not_implemented")) {
        emit notImplemented(QStringLiteral("settings"));
        return;
    }
    if (!response.contains(QStringLiteral("enabled"))) {
        emit failed(QStringLiteral("UNKNOWN_RESPONSE"),
                    tr("同步设置响应格式无法识别"));
        return;
    }
    emit settingsResult(response);
}
