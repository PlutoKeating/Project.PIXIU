#include "app/ForgetController.h"

#include <QLoggingCategory>

#include "services/BackendTransport.h"

Q_LOGGING_CATEGORY(lcForget, "pixiu.forget")

ForgetController::ForgetController(BackendTransport *transport, QObject *parent)
    : QObject(parent)
    , m_transport(transport)
{
    connect(m_transport, &BackendTransport::forgetResult,
            this, &ForgetController::handleForgetResult);
    connect(m_transport, &BackendTransport::errorOccurred, this,
            [this](const QString &code, const QString &message, const QString &) {
                if (!m_pendingCommand.isEmpty()) {
                    emit failed(code, message);
                }
            });
}

bool ForgetController::isForgetIntent(const QString &text)
{
    const QString trimmed = text.trimmed();
    return trimmed.startsWith(QStringLiteral("忘记"))
        || trimmed.startsWith(QStringLiteral("遗忘"))
        || trimmed.startsWith(QStringLiteral("忘了"));
}

void ForgetController::requestConfirmation(const QString &command)
{
    m_pendingCommand = command.trimmed();
    if (m_pendingCommand.isEmpty()) {
        return;
    }
    qCInfo(lcForget) << "requesting forget confirmation (confirm=false)";
    m_transport->forget(m_pendingCommand, false);
}

void ForgetController::confirm()
{
    if (m_pendingCommand.isEmpty()) {
        return;
    }
    qCInfo(lcForget) << "confirming forget (confirm=true)";
    m_transport->forget(m_pendingCommand, true);
}

void ForgetController::confirmRemote(const QString &command)
{
    const QString trimmed = command.trimmed();
    if (trimmed.isEmpty()) {
        return;
    }
    m_pendingCommand = trimmed;
    qCInfo(lcForget) << "confirming remote forget (confirm=true):" << trimmed;
    m_transport->forget(m_pendingCommand, true);
}

void ForgetController::cancel()
{
    qCInfo(lcForget) << "forget confirmation cancelled";
    m_pendingCommand.clear();
}

void ForgetController::handleForgetResult(const QJsonObject &response)
{
    if (m_pendingCommand.isEmpty()) {
        return; // 无在途遗忘流程，忽略过期响应
    }

    if (response.contains(QStringLiteral("targets"))) {
        emit confirmationReady(m_pendingCommand, response);
        return;
    }

    if (response.value(QStringLiteral("status")).toString()
        == QStringLiteral("forgotten")) {
        emit forgotten(response);
        m_pendingCommand.clear();
        return;
    }

    emit failed(QStringLiteral("UNKNOWN_RESPONSE"),
                tr("遗忘响应格式无法识别"));
}
