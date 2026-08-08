#ifndef PIXIU_MEMORY_ATOM_H
#define PIXIU_MEMORY_ATOM_H

#include <QJsonArray>
#include <QJsonObject>
#include <QString>
#include <QStringList>

// /memory/query 响应模型（对齐 docs/API.md 3.2）。
//
// 解析规则：只读取契约必需字段，容忍未知/缺失字段与类型偏差。
struct MemoryAtom
{
    QString answer;
    QStringList sourceEvidence;   // source_evidence[]
    QString sourceKnowledge;      // source_knowledge
    double confidence = 0.0;
    int latencyMs = 0;

    bool hasAnswer() const { return !answer.isEmpty(); }

    static MemoryAtom fromJson(const QJsonObject &obj)
    {
        MemoryAtom atom;
        atom.answer = obj.value(QStringLiteral("answer")).toString();
        atom.sourceKnowledge =
            obj.value(QStringLiteral("source_knowledge")).toString();
        atom.confidence =
            obj.value(QStringLiteral("confidence")).toDouble(0.0);
        atom.latencyMs =
            obj.value(QStringLiteral("latency_ms")).toInt(0);

        const QJsonArray evidence =
            obj.value(QStringLiteral("source_evidence")).toArray();
        atom.sourceEvidence.reserve(evidence.size());
        for (const QJsonValue &value : evidence) {
            const QString id = value.toString();
            if (!id.isEmpty()) {
                atom.sourceEvidence.append(id);
            }
        }
        return atom;
    }
};

#endif // PIXIU_MEMORY_ATOM_H
