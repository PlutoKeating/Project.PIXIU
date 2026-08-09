#include "app/WriteController.h"

#include <QJsonObject>

#include "services/BackendTransport.h"

WriteController::WriteController(BackendTransport *transport, QObject *parent)
    : QObject(parent)
    , m_transport(transport)
{
    connect(m_transport, &BackendTransport::writeAcknowledged,
            this, [this](const QJsonObject &response) {
                m_busy = false;
                emit writeAccepted(response);
            });
    // 写入错误走通用 errorOccurred（写入请求不带查询 tag）；仅在在途时
    // 上抛，避免其他端点（冲突/偏好/配对等）的错误串扰写入失败反馈。
    connect(m_transport, &BackendTransport::errorOccurred, this,
            [this](const QString &code, const QString &message, const QString &) {
                if (!m_busy) {
                    return;
                }
                m_busy = false;
                emit writeFailed(code, message);
            });
}

bool WriteController::submit(const QString &title,
                             const QString &content,
                             const QString &scope,
                             const QString &imagePath)
{
    if (m_busy) {
        return false;
    }
    m_busy = true;

    QJsonObject raw;
    raw.insert(QStringLiteral("title"), title);
    raw.insert(QStringLiteral("body"),
               QJsonObject{{QStringLiteral("text"), content}});

    QJsonObject payload;
    payload.insert(QStringLiteral("source_type"), QStringLiteral("MANUAL_CONFIG"));
    payload.insert(QStringLiteral("raw"), raw);
    payload.insert(QStringLiteral("scope"), scope);

    QJsonObject context;
    if (!imagePath.isEmpty()) {
        // 附件预览信息放入 context（OCR 接入后由后端识别结构化）。
        context.insert(QStringLiteral("attachment_path"), imagePath);
        context.insert(QStringLiteral("ocr_pending"), true);
    }
    if (!context.isEmpty()) {
        payload.insert(QStringLiteral("context"), context);
    }
    m_transport->writeMemory(payload);
    return true;
}

bool WriteController::isBusy() const
{
    return m_busy;
}
