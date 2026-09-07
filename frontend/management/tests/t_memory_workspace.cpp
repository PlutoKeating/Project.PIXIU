#include "MemoryWorkspace.h"
#include "MemoryWriteDialog.h"
#include "services/HttpBackendTransport.h"
#include <QComboBox>
#include <QLabel>
#include <QLineEdit>
#include <QListWidget>
#include <QPlainTextEdit>
#include <QPushButton>
#include <QTest>
#include <QSignalSpy>

class Transport : public HttpBackendTransport
{
public:
    quint64 queryMemory(const QString &text, const QJsonObject &hint) override
    { query = text; scope = hint; return ++sequence; }
    void evidenceDetail(const QString &id) override { evidence = id; }
    void writeMemory(const QJsonObject &payload) override { written = payload; ++writes; }
    QJsonObject written;
    int writes = 0;
    quint64 sequence = 0;
    QString query, evidence;
    QJsonObject scope;
};

class WorkspaceTest : public QObject
{
    Q_OBJECT
private slots:
    void writeRetainsInputAndRetriesIdempotently()
    {
        Transport transport;
        pixiu::MemoryWriteDialog dialog(nullptr, &transport);
        auto *title = dialog.findChild<QLineEdit *>("writeTitle");
        auto *body = dialog.findChild<QPlainTextEdit *>("writeBody");
        auto *save = dialog.findChild<QPushButton *>("writeSave");
        QVERIFY(!save->isEnabled());
        title->setText("Example");
        body->setPlainText("Remember this");
        save->click();
        QCOMPARE(transport.written.value("raw").toObject().value("body").toObject().value("text").toString(), QStringLiteral("Remember this"));
        const QString key = transport.written.value("idempotency_key").toString();
        QVERIFY(!key.isEmpty());
        save->click();
        QCOMPARE(transport.writes, 1);
        emit transport.errorOccurred("TIMEOUT", "retry", "");
        QCOMPARE(body->toPlainText(), QStringLiteral("Remember this"));
        save->click();
        QCOMPARE(transport.writes, 2);
        QCOMPARE(transport.written.value("idempotency_key").toString(), key);
        emit transport.writeAcknowledged({{"status", "unexpected"}});
        QCOMPARE(body->toPlainText(), QStringLiteral("Remember this"));
        body->setPlainText("Changed");
        save->click();
        QVERIFY(transport.written.value("idempotency_key").toString() != key);
        QSignalSpy accepted(&dialog, &pixiu::MemoryWriteDialog::memoryAccepted);
        emit transport.writeAcknowledged({{"status", "accepted"}, {"evidence_id", "new-evidence"}});
        QCOMPARE(accepted.count(), 1);
        QVERIFY(body->toPlainText().isEmpty());
        QVERIFY(!save->isEnabled());
    }
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
        sources->setCurrentRow(-1);
        sources->setCurrentRow(0);
        emit transport.evidenceDetailResult({{"id", "e1"}, {"raw", QJsonObject{{"body", QJsonObject{{"text", "结构化正文"}}}}}});
        QCOMPARE(workspace.findChild<QPlainTextEdit *>("memoryEvidence")->toPlainText(), QStringLiteral("结构化正文"));
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
