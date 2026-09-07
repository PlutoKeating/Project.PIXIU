#include "MemoryWorkspace.h"
#include "services/HttpBackendTransport.h"
#include <QComboBox>
#include <QLabel>
#include <QLineEdit>
#include <QListWidget>
#include <QPlainTextEdit>
#include <QPushButton>
#include <QTest>

class Transport : public HttpBackendTransport
{
public:
    quint64 queryMemory(const QString &text, const QJsonObject &hint) override
    { query = text; scope = hint; return ++sequence; }
    void evidenceDetail(const QString &id) override { evidence = id; }
    quint64 sequence = 0;
    QString query, evidence;
    QJsonObject scope;
};

class WorkspaceTest : public QObject
{
    Q_OBJECT
private slots:
    void searchAndEvidence()
    {
        Transport transport;
        QWidget host;
        pixiu::MemoryWorkspace workspace(&host, &transport);
        QVERIFY(!workspace.isWindow());
        auto *input = workspace.findChild<QLineEdit *>("memoryQuery");
        auto *search = workspace.findChild<QPushButton *>("memorySearch");
        input->setText(QStringLiteral("账单"));
        search->click();
        QCOMPARE(transport.query, QStringLiteral("账单"));
        QVERIFY(!search->isEnabled());
        emit transport.queryResult(transport.sequence, {{"answer", "434.50"}, {"source_evidence", QJsonArray{"e1"}}});
        QCOMPARE(workspace.findChild<QPlainTextEdit *>("memoryAnswer")->toPlainText(), QStringLiteral("434.50"));
        auto *sources = workspace.findChild<QListWidget *>("memorySources");
        QCOMPARE(sources->count(), 1);
        sources->setCurrentRow(0);
        QCOMPARE(transport.evidence, QStringLiteral("e1"));
        QVERIFY(!sources->isEnabled());
        emit transport.errorOccurred("TIMEOUT", "offline", "request");
        QVERIFY(sources->isEnabled());
        QCOMPARE(sources->currentRow(), -1);
        sources->setCurrentRow(0);
        emit transport.evidenceDetailResult({{"id", "e1"}, {"raw", QJsonObject{{"title", "账单"}, {"body", "真实正文"}}}});
        QVERIFY(sources->isEnabled());
        QCOMPARE(workspace.findChild<QPlainTextEdit *>("memoryEvidence")->toPlainText(), QStringLiteral("真实正文"));
    }
    void scopeChangeRejectsOldResponse()
    {
        Transport transport;
        pixiu::MemoryWorkspace workspace(nullptr, &transport);
        workspace.findChild<QLineEdit *>("memoryQuery")->setText("test");
        auto *search = workspace.findChild<QPushButton *>("memorySearch");
        search->click();
        workspace.findChild<QComboBox *>("memoryScope")->setCurrentIndex(2);
        emit transport.queryResult(1, {{"answer", "stale"}});
        QVERIFY(workspace.findChild<QPlainTextEdit *>("memoryAnswer")->toPlainText().isEmpty());
        search->click();
        QCOMPARE(transport.scope.value("scope").toString(), QStringLiteral("shared:home"));
        emit transport.queryFailed(2, "TIMEOUT", "offline");
        QVERIFY(search->isEnabled());
        QCOMPARE(workspace.findChild<QLineEdit *>("memoryQuery")->text(), QStringLiteral("test"));
        QVERIFY(workspace.findChild<QLabel *>("memoryStatus")->text().contains("offline"));
    }
};
QTEST_MAIN(WorkspaceTest)
#include "t_memory_workspace.moc"
