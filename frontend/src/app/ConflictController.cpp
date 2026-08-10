#include "app/ConflictController.h"

#include <QLoggingCategory>

#include "services/BackendTransport.h"

Q_LOGGING_CATEGORY(lcConflicts, "pixiu.conflicts")

ConflictController::ConflictController(BackendTransport *transport, QObject *parent)
    : QObject(parent)
    , m_transport(transport)
{
    connect(m_transport, &BackendTransport::conflictsResult, this,
            [this](const QJsonArray &conflicts) {
                if (!m_inFlight) {
                    return;
                }
                m_inFlight = false;
                emit conflictsLoaded(conflicts);
            });
    connect(m_transport, &BackendTransport::errorOccurred, this,
            [this](const QString &code, const QString &message, const QString &) {
                if (!m_inFlight) {
                    return;
                }
                m_inFlight = false;
                emit failed(code, message);
            });
}

void ConflictController::refresh()
{
    if (m_inFlight) {
        return; // 在途防重：避免重复拉取；在途响应会刷新面板
    }
    m_inFlight = true;
    m_transport->listConflicts();
}
