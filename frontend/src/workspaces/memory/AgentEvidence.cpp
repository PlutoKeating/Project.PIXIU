#include "AgentEvidence.h"
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QRegularExpression>
#include <QSet>

namespace pixiu {
AgentEvidenceResult parseAgentEvidence(const QByteArray &response, const QString &sessionId,
                                      const QString &scope)
{
    if (response.size() > 2*1024*1024) return {AgentEvidenceResult::TooLarge, {}};
    const QRegularExpression safeSession(QStringLiteral("\\A[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\\z"));
    const QRegularExpression safeScope(QStringLiteral("\\A(user|shared):[A-Za-z0-9._-]+\\z"));
    if (!safeSession.match(sessionId).hasMatch() || !safeScope.match(scope).hasMatch()) return {};
    const auto document = QJsonDocument::fromJson(response);
    const auto root = document.object();
    if (!document.isObject() || root.value("session_id").toString() != sessionId ||
        !root.value("content").isString()) return {};
    AgentEvidenceResult parsed{AgentEvidenceResult::Ready, {}};
    QSet<QString> started;
    QSet<QString> completed;
    const QRegularExpression knowledgeId(QStringLiteral("\\Aknw_[A-Za-z0-9_-]{8,128}\\z"));
    const QRegularExpression evidenceId(QStringLiteral("\\Aevd_[A-Za-z0-9_-]{8,128}\\z"));
    for (const auto &line : root.value("content").toString().split('\n')) {
        if (line.trimmed().isEmpty()) continue;
        const auto eventDocument = QJsonDocument::fromJson(line.toUtf8());
        if (!eventDocument.isObject()) return {};
        const auto event = eventDocument.object();
        const auto data = event.value("data").toObject();
        if (data.value("name").toString() != "pixiu_memory_search") continue;
        // Branch traces can share the parent's file. Do not attribute them to
        // this session without a separately verified child-session association.
        if (data.value("scope").toString() == "branch" || !data.value("subagent_id").toString().isEmpty()) continue;
        const auto call = data.value("tool_call_id").toString();
        if (call.isEmpty() || call.size() > 256) continue;
        if (event.value("event").toString() == "gateway.tool.started") {
            started.insert(call);
            continue;
        }
        if (event.value("event").toString() != "gateway.tool.completed" ||
            !started.contains(call) || completed.contains(call)) continue;
        completed.insert(call);
        auto resultValue = data.value("result");
        if (resultValue.isString()) {
            const auto decoded = QJsonDocument::fromJson(resultValue.toString().toUtf8());
            if (!decoded.isObject()) return {};
            resultValue = decoded.object();
        }
        if (!resultValue.isObject()) return {};
        const auto result = resultValue.toObject();
        if (result.contains("error")) continue;
        if (result.value("session_id").toString() != sessionId ||
            !safeSession.match(result.value("turn_id").toString()).hasMatch() ||
            !result.value("items").isArray()) return {};
        for (const auto &value : result.value("items").toArray()) {
            const auto item = value.toObject();
            if (item.value("scope").toString() != scope) continue;
            const auto knowledge = item.value("knowledge_id").toString();
            if (!knowledgeId.match(knowledge).hasMatch() || !item.value("evidence_ids").isArray()) return {};
            QSet<QString> seen;
            for (const auto &idValue : item.value("evidence_ids").toArray()) {
                const auto id = idValue.toString();
                if (!evidenceId.match(id).hasMatch()) return {};
                if (seen.contains(id)) continue;
                seen.insert(id);
                if (parsed.references.size() == 256) return {AgentEvidenceResult::TooLarge, {}};
                parsed.references.append({id, knowledge, item.value("title").toString().left(512),
                    scope, result.value("turn_id").toString(), call});
            }
        }
    }
    return parsed;
}
}
