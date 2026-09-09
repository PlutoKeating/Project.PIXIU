#pragma once
#include <QByteArray>
#include <QString>
#include <QStringList>
#include <QVector>

namespace pixiu {
struct AgentEvidenceReference {
    QString evidenceId;
    QString knowledgeId;
    QString title;
    QString scope;
    QString turnId;
    QString callId;
};
struct AgentEvidenceResult {
    enum Status { Ready, Invalid, TooLarge } status = Invalid;
    QVector<AgentEvidenceReference> references;
    QStringList readScopes;
};
// Runtime details are a best-effort trace, not the memory database. Empty Ready
// means no verified references in this trace, not that the session used no memory.
AgentEvidenceResult parseAgentEvidence(const QByteArray &response,
    const QString &sessionId, const QString &scope);
}
