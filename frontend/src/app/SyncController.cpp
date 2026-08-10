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
    connect(m_transport, &BackendTransport::errorOccurred, this,
            [this](const QString &code, const QString &message, const QString &) {
                // 通用错误通道：仅处理同步管理相关的在途请求，避免误吞
                // 配对/写入/冲突等其他端点的错误。
                if (!m_peersPending && !m_statusPending && !m_revokePending) {
                    return;
                }
                m_peersPending = false;
                m_statusPending = false;
                m_revokePending = false;
                m_revokePeerId.clear();
                emit failed(code, message);
            });
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
