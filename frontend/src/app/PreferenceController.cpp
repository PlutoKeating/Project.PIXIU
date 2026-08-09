#include "app/PreferenceController.h"

#include <QLoggingCategory>

#include "services/BackendTransport.h"

Q_LOGGING_CATEGORY(lcPreference, "pixiu.preference")

PreferenceController::PreferenceController(BackendTransport *transport, QObject *parent)
    : QObject(parent)
    , m_transport(transport)
{
    connect(m_transport, &BackendTransport::preferenceHistoryResult, this,
            [this](const QJsonObject &response) {
                if (m_pendingId.isEmpty()) {
                    return; // 无在途请求，忽略过期响应
                }
                m_pendingId.clear();
                emit historyLoaded(response);
            });
    connect(m_transport, &BackendTransport::errorOccurred, this,
            [this](const QString &code, const QString &message, const QString &) {
                if (m_pendingId.isEmpty()) {
                    return;
                }
                m_pendingId.clear();
                emit failed(code, message);
            });
}

void PreferenceController::loadHistory(const QString &preferenceId)
{
    const QString id = preferenceId.trimmed();
    if (id.isEmpty()) {
        return;
    }
    if (!m_pendingId.isEmpty()) {
        return; // 在途防重：避免过期响应被误配到新请求
    }
    m_pendingId = id;
    qCInfo(lcPreference) << "loading preference history:" << id;
    m_transport->preferenceHistory(id);
}
