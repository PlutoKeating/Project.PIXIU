#include "AgentEvidence.h"
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QTest>

class AgentEvidenceTest : public QObject {
    Q_OBJECT
    QJsonObject result() const {
        return {{"session_id", "session-1"}, {"turn_id", "turn-1"},
            {"items", QJsonArray{QJsonObject{{"knowledge_id", "knw_example01"},
                {"title", "A remembered fact"}, {"scope", "user:local"},
                {"evidence_ids", QJsonArray{"evd_example01"}}}}}};
    }
    QJsonObject event(const QString &type, const QJsonValue &value = {}) const {
        return {{"event", type}, {"data", QJsonObject{{"name", "pixiu_memory_search"},
            {"tool_call_id", "call-1"}, {"result", value}}}};
    }
    QByteArray response(const QJsonArray &events, const QString &session = "session-1") const {
        QString content;
        for (const auto &entry : events)
            content += QString::fromUtf8(QJsonDocument(entry.toObject()).toJson(QJsonDocument::Compact)) + '\n';
        return QJsonDocument(QJsonObject{{"session_id", session}, {"content", content}}).toJson();
    }
private slots:
    void verifiedToolResult() {
        auto completed = event("gateway.tool.completed",
            QString::fromUtf8(QJsonDocument(result()).toJson(QJsonDocument::Compact)));
        const auto parsed = pixiu::parseAgentEvidence(response({event("gateway.tool.started"), completed}), "session-1", "user:local");
        QCOMPARE(parsed.status, pixiu::AgentEvidenceResult::Ready);
        QCOMPARE(parsed.references.size(), 1);
        QCOMPARE(parsed.references[0].evidenceId, QString("evd_example01"));
        QCOMPARE(parsed.references[0].title, QString("A remembered fact"));
        QCOMPARE(parsed.references[0].callId, QString("call-1"));
    }
    void rejectsUncorrelatedAndWrongScope() {
        auto completed = event("gateway.tool.completed", result());
        QCOMPARE(pixiu::parseAgentEvidence(response({completed}), "session-1", "user:local").references.size(), 0);
        QCOMPARE(pixiu::parseAgentEvidence(response({event("gateway.tool.started"), completed}), "session-1", "shared:home").references.size(), 0);
        QCOMPARE(pixiu::parseAgentEvidence(response({completed}, "other"), "session-1", "user:local").status, pixiu::AgentEvidenceResult::Invalid);
    }
    void ignoresModelTextAndDuplicateCompletion() {
        auto completed = event("gateway.tool.completed", result());
        const auto parsed = pixiu::parseAgentEvidence(response({QJsonObject{{"event", "agent.completed"},
            {"text", "evd_fake00001"}}, event("gateway.tool.started"), completed, completed}), "session-1", "user:local");
        QCOMPARE(parsed.references.size(), 1);
    }
    void rejectsMalformedAndOversized() {
        QCOMPARE(pixiu::parseAgentEvidence("{}", "session-1", "user:local").status, pixiu::AgentEvidenceResult::Invalid);
        QCOMPARE(pixiu::parseAgentEvidence(QByteArray(2*1024*1024+1, 'x'), "session-1", "user:local").status, pixiu::AgentEvidenceResult::TooLarge);
    }
    void rejectsCrossSessionResultAndMalformedId() {
        auto other = result();
        other["session_id"] = "other";
        QCOMPARE(pixiu::parseAgentEvidence(response({event("gateway.tool.started"),
            event("gateway.tool.completed", other)}), "session-1", "user:local").status, pixiu::AgentEvidenceResult::Invalid);
        auto items = result()["items"].toArray();
        auto item = items[0].toObject();
        item["evidence_ids"] = QJsonArray{"../../private"};
        other = result();
        other["items"] = QJsonArray{item};
        QCOMPARE(pixiu::parseAgentEvidence(response({event("gateway.tool.started"),
            event("gateway.tool.completed", other)}), "session-1", "user:local").status, pixiu::AgentEvidenceResult::Invalid);
    }
    void rejectsMalformedTraceAndCapsReferences() {
        auto bad = QJsonDocument(QJsonObject{{"session_id", "session-1"}, {"content", "{unfinished"}}).toJson();
        QCOMPARE(pixiu::parseAgentEvidence(bad, "session-1", "user:local").status, pixiu::AgentEvidenceResult::Invalid);
        auto item = result()["items"].toArray()[0].toObject();
        QJsonArray ids;
        for (int i = 0; i < 257; ++i) ids.append(QString("evd_example%1").arg(i));
        item["evidence_ids"] = ids;
        auto many = result();
        many["items"] = QJsonArray{item};
        const auto parsed = pixiu::parseAgentEvidence(response({event("gateway.tool.started"),
            event("gateway.tool.completed", many)}), "session-1", "user:local");
        QCOMPARE(parsed.status, pixiu::AgentEvidenceResult::TooLarge);
        QVERIFY(parsed.references.isEmpty());
    }
    void ignoresBranchAndOtherTools() {
        auto complete = event("gateway.tool.completed", result());
        auto data = complete["data"].toObject();
        data["scope"] = "branch";
        complete["data"] = data;
        QVERIFY(pixiu::parseAgentEvidence(response({event("gateway.tool.started"), complete}), "session-1", "user:local").references.isEmpty());
        data.remove("scope");
        data["name"] = "terminal";
        complete["data"] = data;
        QVERIFY(pixiu::parseAgentEvidence(response({event("gateway.tool.started"), complete}), "session-1", "user:local").references.isEmpty());
    }
};
QTEST_GUILESS_MAIN(AgentEvidenceTest)
#include "t_agent_evidence.moc"
