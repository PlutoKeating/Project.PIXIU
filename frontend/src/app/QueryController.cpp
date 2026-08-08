#include "app/QueryController.h"

#include <QJsonObject>
#include <QLoggingCategory>

#include "services/BackendTransport.h"

Q_LOGGING_CATEGORY(lcQuery, "pixiu.query")

QueryController::QueryController(BackendTransport *transport, QObject *parent)
    : QObject(parent)
    , m_transport(transport)
{
}

void QueryController::submit(const QString &text)
{
    m_pendingSequence = ++m_sequence;
    m_pendingText = text;

    emit userMessageReady(text);
    emit thinkingChanged(true);

    QJsonObject contextHint;
    contextHint.insert(QStringLiteral("top_k"), 5);
    m_pendingRequestId = m_transport->queryMemory(text, contextHint);
}

void QueryController::handleQueryResult(quint64 requestId, const QJsonObject &atom)
{
    if (m_pendingSequence < 0 || requestId != m_pendingRequestId) {
        return; // 无在途查询
    }

    const MemoryAtom memory = MemoryAtom::fromJson(atom);
    m_pendingSequence = -1;
    m_pendingRequestId = 0;
    m_pendingText.clear();
    emit thinkingChanged(false);

    if (memory.hasAnswer()) {
        emit answerReady(memory);
    } else {
        emit emptyResultReady();
    }
}

void QueryController::handleQueryError(quint64 requestId,
                                       const QString &code,
                                       const QString &message)
{
    if (m_pendingSequence < 0 || requestId != m_pendingRequestId) {
        return; // 非查询错误（如健康探测失败）不打断对话
    }

    const QString failedText = m_pendingText;
    m_pendingSequence = -1;
    m_pendingRequestId = 0;
    m_pendingText.clear();
    emit thinkingChanged(false);
    emit queryFailed(failedText, code, message);
}
