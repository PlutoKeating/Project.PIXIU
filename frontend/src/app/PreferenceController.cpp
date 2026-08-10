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
    connect(m_transport, &BackendTransport::preferenceExtractResult, this,
            [this](const QJsonObject &response) {
                if (!m_extractPending) {
                    return; // 无在途提取，忽略过期响应
                }
                m_extractPending = false;
                const int count =
                    response.value(QStringLiteral("extracted_preferences"))
                        .toArray()
                        .size();
                emit extracted(count,
                               response.value(QStringLiteral("latency_ms")).toInt(0));
            });
    connect(m_transport, &BackendTransport::errorOccurred, this,
            [this](const QString &code, const QString &message, const QString &) {
                if (m_extractPending) {
                    m_extractPending = false;
                    emit extractFailed(code, message);
                    return;
                }
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

void PreferenceController::extract(const QStringList &evidenceIds)
{
    if (evidenceIds.isEmpty() || m_extractPending) {
        return;
    }
    m_extractPending = true;

    QJsonArray ids;
    for (const QString &id : evidenceIds) {
        ids.append(id);
    }
    QJsonObject payload;
    payload.insert(QStringLiteral("evidence_ids"), ids);
    m_transport->extractPreferences(payload);
}
