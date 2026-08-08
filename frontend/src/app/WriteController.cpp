#include "app/WriteController.h"

#include <QJsonObject>

#include "services/BackendTransport.h"

WriteController::WriteController(BackendTransport *transport, QObject *parent)
    : QObject(parent)
    , m_transport(transport)
{
    connect(m_transport, &BackendTransport::writeAcknowledged,
            this, &WriteController::writeAccepted);
    // 写入错误走通用 errorOccurred（写入请求不带查询 tag）。
    connect(m_transport, &BackendTransport::errorOccurred, this,
            [this](const QString &code, const QString &message, const QString &) {
                emit writeFailed(code, message);
            });
}

void WriteController::submit(const QString &title,
                             const QString &content,
                             const QString &scope,
                             const QString &imagePath)
{
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
}
