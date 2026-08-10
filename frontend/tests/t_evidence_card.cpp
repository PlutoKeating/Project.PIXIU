#include <QSignalSpy>
#include <QTest>

#include "widgets/EvidenceCard.h"

// EvidenceCard 交互测试：左键点击发射证据 ID，右键不发射。
class TestEvidenceCard : public QObject
{
    Q_OBJECT

private slots:
    void leftClickEmitsEvidenceId();
    void rightClickDoesNotEmit();
};

void TestEvidenceCard::leftClickEmitsEvidenceId()
{
    EvidenceCard card(QStringLiteral("evd_01H"), 0.93, 210);
    QSignalSpy spy(&card, &EvidenceCard::evidenceClicked);
    QTest::mouseClick(&card, Qt::LeftButton);
    QCOMPARE(spy.count(), 1);
    QCOMPARE(spy.takeFirst().at(0).toString(), QStringLiteral("evd_01H"));
}

void TestEvidenceCard::rightClickDoesNotEmit()
{
    EvidenceCard card(QStringLiteral("evd_01H"), 0.93, 210);
    QSignalSpy spy(&card, &EvidenceCard::evidenceClicked);
    QTest::mouseClick(&card, Qt::RightButton);
    QCOMPARE(spy.count(), 0);
}

QTEST_MAIN(TestEvidenceCard)
#include "t_evidence_card.moc"
