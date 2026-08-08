#include <QJsonArray>
#include <QJsonObject>
#include <QTest>

#include "models/MemoryAtom.h"

// MemoryAtom JSON 解析契约测试（对齐 docs/API.md 3.2）：
// 只读取必需字段、容忍未知字段与缺失字段、过滤空证据 ID。
class TestMemoryAtom : public QObject
{
    Q_OBJECT

private slots:
    void parsesFullContract();
    void missingFieldsFallbackToDefaults();
    void unknownFieldsAreTolerated();
    void emptyAnswerHasNoAnswer();
    void emptyEvidenceIdsAreFiltered();
};

void TestMemoryAtom::parsesFullContract()
{
    QJsonObject obj{
        {QStringLiteral("answer"),
         QStringLiteral("2026年4月，你们在水电燃气方面共支出 434.50 元")},
        {QStringLiteral("source_evidence"),
         QJsonArray{QStringLiteral("evd_01H"), QStringLiteral("evd_02K")}},
        {QStringLiteral("source_knowledge"), QStringLiteral("knw_02K")},
        {QStringLiteral("confidence"), 0.93},
        {QStringLiteral("latency_ms"), 210}};

    const MemoryAtom atom = MemoryAtom::fromJson(obj);

    QCOMPARE(atom.answer,
             QStringLiteral("2026年4月，你们在水电燃气方面共支出 434.50 元"));
    QCOMPARE(atom.sourceEvidence,
             QStringList({QStringLiteral("evd_01H"), QStringLiteral("evd_02K")}));
    QCOMPARE(atom.sourceKnowledge, QStringLiteral("knw_02K"));
    QVERIFY(qAbs(atom.confidence - 0.93) < 1e-9);
    QCOMPARE(atom.latencyMs, 210);
    QVERIFY(atom.hasAnswer());
}

void TestMemoryAtom::missingFieldsFallbackToDefaults()
{
    const MemoryAtom atom = MemoryAtom::fromJson(QJsonObject{});

    QVERIFY(atom.answer.isEmpty());
    QVERIFY(atom.sourceEvidence.isEmpty());
    QVERIFY(atom.sourceKnowledge.isEmpty());
    QVERIFY(qAbs(atom.confidence) < 1e-9);
    QCOMPARE(atom.latencyMs, 0);
    QVERIFY(!atom.hasAnswer());
}

void TestMemoryAtom::unknownFieldsAreTolerated()
{
    QJsonObject obj{
        {QStringLiteral("answer"), QStringLiteral("答案")},
        {QStringLiteral("extra_field"), QStringLiteral("future contract field")},
        {QStringLiteral("nested"), QJsonObject{{QStringLiteral("x"), 1}}}};

    const MemoryAtom atom = MemoryAtom::fromJson(obj);
    QCOMPARE(atom.answer, QStringLiteral("答案"));
    QVERIFY(atom.hasAnswer());
}

void TestMemoryAtom::emptyAnswerHasNoAnswer()
{
    QJsonObject obj{
        {QStringLiteral("answer"), QString()},
        {QStringLiteral("source_evidence"), QJsonArray{}}};

    const MemoryAtom atom = MemoryAtom::fromJson(obj);
    QVERIFY(!atom.hasAnswer());
}

void TestMemoryAtom::emptyEvidenceIdsAreFiltered()
{
    QJsonObject obj{
        {QStringLiteral("answer"), QStringLiteral("答案")},
        {QStringLiteral("source_evidence"),
         QJsonArray{QStringLiteral("evd_01H"), QString(), QStringLiteral("")}}};

    const MemoryAtom atom = MemoryAtom::fromJson(obj);
    QCOMPARE(atom.sourceEvidence, QStringList({QStringLiteral("evd_01H")}));
}

QTEST_MAIN(TestMemoryAtom)
#include "t_memory_atom.moc"
