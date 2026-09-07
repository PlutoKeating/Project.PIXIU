#include "MemoryWorkspace.h"
#include "MemoryScopes.h"
#include "MemoryWriteDialog.h"
#include "MemoryEditDialog.h"
#include "MemoryAudit.h"
#include "PrivacyPage.h"
#include "DevicePage.h"
#include "DeliveryPage.h"
#include "ForgetPage.h"
#include "SettingsWorkspace.h"
#include "ServiceStatusPage.h"
#include "HostCloseGuard.h"
#include "AgentEvidenceClient.h"
#include <QTcpServer>
#include <QTabWidget>
#include "PairingDialog.h"
#include <QMessageBox>
#include <QTimer>
#include <QCheckBox>
#include <QCloseEvent>
#include "services/HttpBackendTransport.h"
#include <QComboBox>
#include <QDateEdit>
#include <QLabel>
#include <QLineEdit>
#include <QListWidget>
#include <QPlainTextEdit>
#include <QPixmap>
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
    QString editId, editScope;
    QJsonObject edited;
    int edits = 0;
    void memoryItem(const QString &id, const QString &scope) override { editId = id; editScope = scope; }
    void updateMemory(const QJsonObject &payload) override { edited = payload; ++edits; }
    QString auditScope, historyId;
    QJsonObject extraction;
    int conflictRequests = 0;
    int statusReads = 0, peerReads = 0, discoveries = 0;
    QJsonObject syncSettings;
    QString revoked;
    QJsonObject tokenRequest, pairRequest;
    int pairCalls = 0;
    int insightReads = 0, digestReads = 0;
    int diagnosticReads = 0;
    void backendDiagnostics() override { ++diagnosticReads; }
    QJsonObject forgetPayload;
    int forgetCalls = 0;
    void reviewedForget(const QJsonObject &payload) override { forgetPayload = payload; ++forgetCalls; }
    void deliveryInsights() override { ++insightReads; }
    QString digestDate;
    void deliveryDigest(const QString &date = QString()) override { ++digestReads; digestDate = date; }
    void createPairingToken(const QJsonObject &payload) override { tokenRequest = payload; }
    void pairDevice(const QJsonObject &payload) override { pairRequest = payload; ++pairCalls; }
    void syncStatus() override { ++statusReads; }
    void listPeers() override { ++peerReads; }
    void discoverDevices() override { ++discoveries; }
    void updateSyncSettings(bool enabled, bool paused) override
    { syncSettings = {{"enabled", enabled}, {"paused", paused}}; }
    void revokePeer(const QString &id) override { revoked = id; }
    QJsonObject savedConfig;
    int configReads = 0, configWrites = 0;
    int logOffset = -1;
    void monitorConfig() override { ++configReads; }
    void updateMonitorConfig(const QJsonObject &payload) override { savedConfig = payload; ++configWrites; }
    void monitorLog(int, int offset) override { logOffset = offset; }
    void preferencesList(const QString &scope) override { auditScope = scope; }
    void preferenceHistory(const QString &id) override { historyId = id; }
    void extractPreferences(const QJsonObject &payload) override { extraction = payload; }
    void listConflicts() override { ++conflictRequests; }
    int writes = 0;
    quint64 sequence = 0;
    QString query, evidence;
    QJsonObject scope;
};

class WorkspaceTest : public QObject
{
    Q_OBJECT
private slots:
    void sessionSourceReadParticipatesInHostExitGuard()
    {
        QWidget host;
        QTcpServer server;
        QVERIFY(server.listen(QHostAddress::LocalHost));
        pixiu::AgentEvidenceClient client(&host);
        pixiu::HostCloseGuard guard(&host);
        client.load(QNetworkRequest(QUrl(QString("http://127.0.0.1:%1").arg(server.serverPort()))),
                    "session-1", "user:local");
        QVERIFY(client.busy());
        QTimer::singleShot(0, [] {
            if (auto *dialog = qobject_cast<QDialog *>(QApplication::activeModalWidget())) dialog->accept();
        });
        QVERIFY(!guard.confirmExit());
        client.cancel();
        QVERIFY(guard.confirmExit());
    }
    void agentSourcesReuseReaderAndValidateFreshEvidence()
    {
        Transport transport;
        pixiu::MemoryWorkspace page(nullptr, &transport);
        auto *sources = page.findChild<QListWidget *>("memorySources");
        auto *detail = page.findChild<QPlainTextEdit *>("memoryEvidence");
        auto *raw = page.findChild<QCheckBox *>("memoryEvidenceRaw");
        pixiu::AgentEvidenceResult result;
        result.status = pixiu::AgentEvidenceResult::Ready;
        result.references.append({"evd_example01", "knw_example01", "<b>source</b>", "user:local", "turn-1", "call-1"});
        result.references.append(result.references.first());
        QVERIFY(page.showAgentSources(result, "user:local"));
        QCOMPARE(sources->count(), 1);
        QCOMPARE(sources->item(0)->text(), QString("<b>source</b>"));
        QVERIFY(detail->toPlainText().isEmpty());
        sources->setCurrentRow(0);
        QCOMPARE(transport.evidence, QString("evd_example01"));
        QVERIFY(page.hasPendingOperation());
        QVERIFY(!page.showAgentSources(result, "user:local"));
        const QJsonObject fresh{{"id", "evd_example01"}, {"scope", "user:local"},
            {"sensitivity", 0}, {"raw", QJsonObject{{"body", "current database text"}}}};
        emit transport.evidenceDetailResult(fresh);
        QVERIFY(!page.hasPendingOperation());
        QVERIFY(detail->toPlainText().contains("current database text"));
        QVERIFY(raw->isEnabled());
        for (const QString &field : {QString("scope"), QString("sensitivity")}) {
            QVERIFY(page.showAgentSources(result, "user:local"));
            sources->setCurrentRow(0);
            auto changed = fresh;
            if (field == "scope") changed.insert(field, "shared:home");
            else changed.insert(field, 1);
            emit transport.evidenceDetailResult(changed);
            QVERIFY(detail->toPlainText().isEmpty());
            QVERIFY(!raw->isEnabled());
            QCOMPARE(sources->currentRow(), -1);
        }
        QVERIFY(page.showAgentSources(result, "user:local"));
        sources->setCurrentRow(0);
        page.clearAgentSources();
        QCOMPARE(sources->count(), 0);
        emit transport.evidenceDetailResult(fresh);
        QVERIFY(detail->toPlainText().isEmpty());
        QVERIFY(!page.hasPendingOperation());
        QVERIFY(!page.showAgentSources(result, "shared:home"));
        result.status = pixiu::AgentEvidenceResult::Invalid;
        QVERIFY(!page.showAgentSources(result, "user:local"));
        result.status = pixiu::AgentEvidenceResult::Ready;
        result.references.clear();
        QVERIFY(page.showAgentSources(result, "user:local"));
        QCOMPARE(sources->count(), 0);
        QVERIFY(page.findChild<QLabel *>("memoryStatus")->text().contains(QStringLiteral("不代表")));
        page.findChild<QLineEdit *>("memoryQuery")->setText("independent search");
        page.findChild<QPushButton *>("memorySearch")->click();
        page.clearAgentSources();
        QVERIFY(page.hasPendingOperation());
        emit transport.queryResult(transport.sequence, {{"answer", "independent result"}});
        QCOMPARE(page.findChild<QPlainTextEdit *>("memoryAnswer")->toPlainText(), QString("independent result"));
    }
    void serviceDiagnosticsAreReadOnlyBoundedAndExplicit()
    {
        Transport transport;
        QWidget host;
        pixiu::ServiceStatusPage page(&host, &transport);
        pixiu::HostCloseGuard guard(&host);
        auto *refresh = page.findChild<QPushButton *>("serviceRefresh");
        auto *details = page.findChild<QPlainTextEdit *>("serviceDetails");
        auto *status = page.findChild<QLabel *>("serviceStatus");
        QVERIFY(!page.isWindow());
        QVERIFY(details->isReadOnly());
        QVERIFY(details->toPlainText().isEmpty());
        QCOMPARE(transport.diagnosticReads, 0);
        refresh->click();
        refresh->click();
        QCOMPARE(transport.diagnosticReads, 1);
        QVERIFY(page.hasPendingOperation());
        QTimer::singleShot(0, []() {
            if (auto *dialog = qobject_cast<QDialog *>(QApplication::activeModalWidget())) dialog->accept();
        });
        QVERIFY(!guard.confirmExit());
        const QJsonObject version{{"component", "pixiu-memory-backend"}, {"product_version", "9.9.9"},
            {"api_version", "0.5.0"}, {"agent_memory_api", 1}, {"schema_version", 12}};
        auto health = version;
        health.insert("status", "ready");
        health.insert("database", "ok");
        const QJsonObject portable{{"configured", "auto"}, {"runtime", "portable"}, {"compliant", false}};
        QJsonObject caps{{"platform", QJsonObject{{"family", "other"}, {"version_major", "24"}, {"v11", false}}},
            {"embedding", portable}, {"vector_store", portable}, {"contest_ready", false}};
        QJsonObject report{{"health", health}, {"version", version}, {"capabilities", caps}};
        emit transport.diagnosticsResult(report);
        QVERIFY(!page.hasPendingOperation());
        QVERIFY(refresh->isEnabled());
        QVERIFY(details->toPlainText().contains(QStringLiteral("配置 auto → 实际 portable")));
        QVERIFY(details->toPlainText().contains(QStringLiteral("产品版本：不一致")));
        QVERIFY(details->toPlainText().contains(QStringLiteral("不作为原生验收")));
        QVERIFY(guard.confirmExit());

        refresh->click();
        QVERIFY(details->toPlainText().isEmpty());
        emit transport.errorOccurred("https://private.invalid", "secret credential", "req");
        QVERIFY(status->text().contains("UNKNOWN_ERROR"));
        QVERIFY(!status->text().contains("private"));
        QVERIFY(!status->text().contains("secret"));
        emit transport.diagnosticsResult(report); // Ignore a late response after failure.
        QVERIFY(details->toPlainText().isEmpty());

        QList<QJsonObject> invalid;
        auto wrong = report;
        wrong.remove("version");
        invalid << wrong;
        wrong = report;
        auto mismatched = health;
        mismatched.insert("product_version", "different");
        wrong.insert("health", mismatched);
        invalid << wrong;
        wrong = report;
        auto contradictory = caps;
        contradictory.insert("contest_ready", true);
        wrong.insert("capabilities", contradictory);
        invalid << wrong;
        for (const auto &value : invalid) {
            refresh->click();
            emit transport.diagnosticsResult(value);
            QVERIFY(details->toPlainText().isEmpty());
            QVERIFY(status->text().contains(QStringLiteral("不能确认")));
            QVERIFY(!page.hasPendingOperation());
        }
        refresh->click();
        auto newer = version;
        newer.insert("api_version", "0.6.0");
        report.insert("version", newer);
        emit transport.diagnosticsResult(report);
        QVERIFY(details->toPlainText().contains(QStringLiteral("不在当前已验证范围")));
        report.insert("version", version);
        const QJsonObject sdk{{"configured", "kylin"}, {"runtime", "kylin"}, {"compliant", true}};
        report.insert("capabilities", QJsonObject{
            {"platform", QJsonObject{{"family", "kylin"}, {"version_major", "11"}, {"v11", true}}},
            {"embedding", sdk}, {"vector_store", sdk}, {"contest_ready", true}});
        refresh->click();
        emit transport.diagnosticsResult(report);
        QVERIFY(details->toPlainText().contains(QStringLiteral("双原生 SDK")));
        QVERIFY(details->toPlainText().contains(QStringLiteral("不代表完整验收通过")));
    }
    void scopesPreserveLocalDomainsAndExposeAgentWithoutImplicitSharing()
    {
        QComboBox query, write, sharedWrite, existingShared, invalid;
        pixiu::populateMemoryScopes(&query, true, false, "user:alice");
        QCOMPARE(query.itemData(0).toString(), QString());
        QCOMPARE(query.itemData(1).toString(), QStringLiteral("user:local"));
        QCOMPARE(query.itemData(2).toString(), QStringLiteral("shared:home"));
        QCOMPARE(query.itemData(3).toString(), QStringLiteral("user:alice"));
        pixiu::populateMemoryScopes(&write, false, true, "user:default");
        QCOMPARE(write.currentData().toString(), QStringLiteral("user:default"));
        pixiu::populateMemoryScopes(&sharedWrite, false, true, "shared:team");
        QCOMPARE(sharedWrite.currentData().toString(), QStringLiteral("user:local"));
        QCOMPARE(sharedWrite.findData("shared:team"), 2);
        pixiu::populateMemoryScopes(&existingShared, false, false, "shared:home");
        QCOMPARE(existingShared.count(), 2);
        QVERIFY(existingShared.itemText(1).contains("Agent"));
        pixiu::populateMemoryScopes(&invalid, false, true, "user:alice\n");
        QCOMPARE(invalid.count(), 2);
        QCOMPARE(invalid.currentData().toString(), QStringLiteral("user:local"));
    }
    void agentScopeReachesEveryManagementRequest()
    {
        const bool hadScope = qEnvironmentVariableIsSet("PIXIU_AGENT_SCOPE");
        const auto savedScope = qgetenv("PIXIU_AGENT_SCOPE");
        qputenv("PIXIU_AGENT_SCOPE", "user:alice");
        Transport queryTransport, writeTransport, auditTransport, forgetTransport;
        QWidget host;
        pixiu::MemoryWorkspace query(&host, &queryTransport);
        pixiu::MemoryWriteDialog write(&host, &writeTransport);
        pixiu::MemoryAudit audit(&host, &auditTransport);
        pixiu::ForgetPage forget(&host, &forgetTransport);
        if (hadScope) qputenv("PIXIU_AGENT_SCOPE", savedScope);
        else qunsetenv("PIXIU_AGENT_SCOPE");
        auto *queryScope = query.findChild<QComboBox *>("memoryScope");
        queryScope->setCurrentIndex(queryScope->findData("user:alice"));
        query.findChild<QLineEdit *>("memoryQuery")->setText("test");
        query.findChild<QPushButton *>("memorySearch")->click();
        QCOMPARE(queryTransport.scope.value("scope").toString(), QStringLiteral("user:alice"));
        write.findChild<QLineEdit *>("writeTitle")->setText("test");
        write.findChild<QPlainTextEdit *>("writeBody")->setPlainText("synthetic content");
        write.findChild<QPushButton *>("writeSave")->click();
        QCOMPARE(writeTransport.written.value("scope").toString(), QStringLiteral("user:alice"));
        auto *auditScope = audit.findChild<QComboBox *>("auditScope");
        auditScope->setCurrentIndex(auditScope->findData("user:alice"));
        QCOMPARE(auditTransport.auditScope, QStringLiteral("user:alice"));
        auto *forgetScope = forget.findChild<QComboBox *>("forgetScope");
        forgetScope->setCurrentIndex(forgetScope->findData("user:alice"));
        forget.findChild<QLineEdit *>("forgetCommand")->setText("forget test");
        forget.findChild<QPushButton *>("forgetPreview")->click();
        QCOMPARE(forgetTransport.forgetPayload.value("scope").toString(), QStringLiteral("user:alice"));
        QVERIFY(!forgetTransport.forgetPayload.value("confirm").toBool());
    }
    void hostCloseWaitsForMemoryReads()
    {
        Transport transport;
        QWidget host;
        pixiu::MemoryWorkspace workspace(&host, &transport);
        pixiu::HostCloseGuard guard(&host);
        host.show();
        workspace.findChild<QLineEdit *>("memoryQuery")->setText("test");
        auto *search = workspace.findChild<QPushButton *>("memorySearch");
        const auto closeWhileBusy = [&]() {
            QTimer::singleShot(0, &host, [&]() {
                if (auto *box = host.findChild<QMessageBox *>()) box->accept();
            });
            return host.close();
        };
        search->click();
        QVERIFY(!closeWhileBusy());
        emit transport.queryResult(transport.sequence + 1, {{"answer", "unrelated"}});
        QVERIFY(!closeWhileBusy());
        emit transport.queryFailed(transport.sequence, "TIMEOUT", "offline");
        QVERIFY(host.close());
        host.show();
        search->click();
        emit transport.queryResult(transport.sequence,
            {{"answer", "test"}, {"source_evidence", QJsonArray{"e1"}}});
        auto *sources = workspace.findChild<QListWidget *>("memorySources");
        sources->setCurrentRow(0);
        QVERIFY(!closeWhileBusy());
        emit transport.errorOccurred("TIMEOUT", "offline", "test");
        QVERIFY(host.close());
        host.show();
        sources->setCurrentRow(0);
        QVERIFY(!closeWhileBusy());
        emit transport.evidenceDetailResult({{"id", "e1"},
            {"raw", QJsonObject{{"body", "test evidence"}}}});
        QVERIFY(host.close());
        QCOMPARE(transport.writes, 0);
    }
    void hostCloseWaitsForDeliveryReads()
    {
        Transport transport;
        QWidget host;
        pixiu::DeliveryPage page(&host, &transport);
        pixiu::HostCloseGuard guard(&host);
        host.show();
        page.findChild<QPushButton *>("deliveryInsights")->click();
        QTimer::singleShot(0, &host, [&]() {
            if (auto *box = host.findChild<QMessageBox *>()) box->accept();
        });
        QVERIFY(!host.close());
        emit transport.insightsResult({});
        QVERIFY(host.close());
        host.show();
        page.findChild<QPushButton *>("deliveryDigest")->click();
        QTimer::singleShot(0, &host, [&]() {
            if (auto *box = host.findChild<QMessageBox *>()) box->accept();
        });
        QVERIFY(!host.close());
        emit transport.errorOccurred("TIMEOUT", "offline", "test");
        QVERIFY(host.close());
        QCOMPARE(transport.insightReads, 1);
        QCOMPARE(transport.digestReads, 1);
    }
    void restartRechecksManagementRequestsAfterDiscardConfirmation()
    {
        Transport transport;
        QWidget host;
        pixiu::MemoryWorkspace workspace(&host, &transport);
        pixiu::HostCloseGuard guard(&host, {}, []() { return true; });
        QDialog restartDialog(&host);
        host.show();
        restartDialog.show();
        workspace.findChild<QLineEdit *>("memoryQuery")->setText("test");
        QTimer::singleShot(0, &host, [&]() {
            workspace.findChild<QPushButton *>("memorySearch")->click();
            host.findChild<QMessageBox *>()->done(QMessageBox::Yes);
        });
        QVERIFY(!guard.confirmExit(&restartDialog));
        QVERIFY(host.isVisible());
        QVERIFY(workspace.hasPendingOperation());
        emit transport.queryResult(transport.sequence, {{"answer", "test"}});
        QTimer::singleShot(0, &host, [&]() {
            host.findChild<QMessageBox *>()->done(QMessageBox::Yes);
        });
        QVERIFY(guard.confirmExit(&restartDialog));
        QVERIFY(host.isVisible());
        QCOMPARE(transport.writes, 0);
    }
    void hostCloseUsesLiveAgentStateWithoutSubmittingOrCancelling()
    {
        QWidget host;
        bool pending = true;
        QString draft = "unsent input";
        pixiu::HostCloseGuard guard(&host, [&]() { return pending; },
            [&]() { return !draft.isEmpty(); });
        host.show();
        QTimer::singleShot(0, &host, [&]() { host.findChild<QMessageBox *>()->accept(); });
        QVERIFY(!host.close());
        QVERIFY(pending);
        QCOMPARE(draft, QStringLiteral("unsent input"));
        pending = false;
        bool defaultCancel = false;
        QTimer::singleShot(0, &host, [&]() {
            auto *question = host.findChild<QMessageBox *>();
            defaultCancel = question->defaultButton() == question->button(QMessageBox::No);
            question->done(QMessageBox::No);
        });
        QVERIFY(!host.close());
        QVERIFY(defaultCancel);
        QCOMPARE(draft, QStringLiteral("unsent input"));
        QTimer::singleShot(0, &host, [&]() {
            pending = true; // State may change in the confirmation's event loop.
            host.findChild<QMessageBox *>()->done(QMessageBox::Yes);
        });
        QVERIFY(!host.close());
        pending = false;
        QTimer::singleShot(0, &host, [&]() { host.findChild<QMessageBox *>()->done(QMessageBox::Yes); });
        QVERIFY(host.close());
        QCOMPARE(draft, QStringLiteral("unsent input")); // Guard only authorizes close, no state mutation.
        draft.clear();
        host.show();
        QVERIFY(host.close());
    }
    void hostClosePreservesPrivacyDraftAndWaitsForResult()
    {
        Transport transport;
        QWidget host;
        pixiu::PrivacyPage page(&host, &transport);
        pixiu::HostCloseGuard guard(&host);
        host.show();
        auto *load = page.findChild<QPushButton *>("privacyLoad");
        auto *save = page.findChild<QPushButton *>("privacySave");
        auto *enabled = page.findChild<QCheckBox *>("privacyEnabled");
        const QJsonObject config{{"enabled", false}, {"directories", QJsonArray{}},
            {"sources", QJsonObject{{"directory", false}, {"behavior", false},
                {"clipboard", false}, {"screenshot", false}}}};
        QVERIFY(!page.hasUnsavedChanges());
        load->click();
        QVERIFY(page.hasPendingOperation());
        emit transport.configResult(config);
        QVERIFY(!page.hasUnsavedChanges());
        enabled->setChecked(true);
        QVERIFY(page.hasUnsavedChanges());
        bool defaultCancel = false;
        bool nestedRejected = false;
        QTimer::singleShot(0, &host, [&]() {
            auto *question = host.findChild<QMessageBox *>();
            QVERIFY(question);
            defaultCancel = question->defaultButton() == question->button(QMessageBox::No);
            QCloseEvent nested;
            QApplication::sendEvent(&host, &nested);
            nestedRejected = !nested.isAccepted();
            question->done(QMessageBox::No);
        });
        QVERIFY(!host.close());
        QVERIFY(defaultCancel);
        QVERIFY(nestedRejected);
        QVERIFY(host.isVisible());
        QCOMPARE(transport.configWrites, 0);
        QVERIFY(enabled->isChecked());
        enabled->setChecked(false);
        QVERIFY(!page.hasUnsavedChanges()); // Returning to the snapshot is not a draft.
        enabled->setChecked(true);
        save->click();
        QTimer::singleShot(0, &host, [&]() { host.findChild<QMessageBox *>()->accept(); });
        QVERIFY(!host.close());
        QCOMPARE(transport.configWrites, 1);
        emit transport.errorOccurred("TIMEOUT", "unknown result", "test");
        QVERIFY(page.hasUnsavedChanges());
        save->click();
        emit transport.configResult(transport.savedConfig);
        QVERIFY(!page.hasPendingOperation());
        QVERIFY(!page.hasUnsavedChanges());
        QVERIFY(host.close());
    }
    void hostCloseRequiresExplicitDiscardAndPreservesBackend()
    {
        Transport transport;
        QWidget host;
        pixiu::DevicePage page(&host, &transport);
        pixiu::HostCloseGuard guard(&host);
        host.show();
        page.findChild<QPushButton *>("deviceRefresh")->click();
        emit transport.syncStatusResult({{"enabled", true}, {"paused", false},
            {"domain", "shared:home"}, {"peers_total", 1},
            {"pending_outgoing_ops", 0}, {"total_ops_synced", 0}});
        emit transport.peersResult({{"peers", QJsonArray{}}});
        auto *paused = page.findChild<QCheckBox *>("devicePaused");
        QVERIFY(!page.hasUnsavedChanges());
        paused->setChecked(true);
        QVERIFY(page.hasUnsavedChanges());
        page.findChild<QPushButton *>("deviceSave")->click();
        QVERIFY(page.hasPendingOperation());
        QTimer::singleShot(0, &host, [&]() { host.findChild<QMessageBox *>()->accept(); });
        QVERIFY(!host.close());
        emit transport.errorOccurred("TIMEOUT", "unknown result", "test");
        QVERIFY(page.hasUnsavedChanges()); // Disabling Save after an error must not lose the draft.
        const auto submitted = transport.syncSettings;
        QTimer::singleShot(0, &host, [&]() { host.findChild<QMessageBox *>()->done(QMessageBox::Yes); });
        QVERIFY(host.close());
        QCOMPARE(transport.syncSettings, submitted); // Discard does not send another write.
    }
    void hostCloseDoesNotBypassOwnedDialog()
    {
        QWidget host;
        pixiu::HostCloseGuard guard(&host);
        QDialog dialog(&host);
        host.show();
        dialog.show();
        QVERIFY(!host.close());
        QVERIFY(dialog.isVisible());
        QVERIFY(host.isVisible());
        dialog.reject();
        QVERIFY(host.close());
    }
    void restartPreflightExcludesOnlyItsInitiatingDialog()
    {
        QWidget host;
        bool pending = true;
        pixiu::HostCloseGuard guard(&host, [&]() { return pending; });
        QDialog restartDialog(&host), otherDialog(&host);
        host.show();
        restartDialog.show();
        QTimer::singleShot(0, &host, [&]() { host.findChild<QMessageBox *>()->accept(); });
        QVERIFY(!guard.confirmExit(&restartDialog));
        pending = false;
        otherDialog.show();
        QVERIFY(!guard.confirmExit(&restartDialog));
        otherDialog.hide();
        QVERIFY(guard.confirmExit(&restartDialog));
        QVERIFY(host.isVisible()); // Preflight must not exit before the helper starts.
        QVERIFY(restartDialog.isVisible());
        QVERIFY(!host.close()); // Ordinary close still cannot bypass the same dialog.
    }
    void hostCloseWaitsForForgetAndPreferenceExtraction()
    {
        Transport forgetTransport, auditTransport;
        QWidget host;
        pixiu::HostCloseGuard guard(&host);
        pixiu::ForgetPage forget(&host, &forgetTransport);
        pixiu::MemoryAudit audit(&host, &auditTransport);
        host.show();
        forget.findChild<QLineEdit *>("forgetCommand")->setText("forget test memory");
        forget.findChild<QPushButton *>("forgetPreview")->click();
        emit forgetTransport.forgetResult({{"targets", QJsonArray{QJsonObject{
            {"id", "k1"}, {"title", "test memory"}, {"version", 1}, {"scope", "user:local"}}}},
            {"confirmation_token", "test-token"}, {"expires_in_seconds", 120}});
        auto *confirm = forget.findChild<QPushButton *>("forgetConfirm");
        QVERIFY(confirm->isEnabled());
        confirm->click();
        QVERIFY(forget.hasPendingOperation());
        QTimer::singleShot(0, &host, [&]() { host.findChild<QMessageBox *>()->accept(); });
        QVERIFY(!host.close());
        QCOMPARE(forgetTransport.forgetCalls, 2);
        emit forgetTransport.errorOccurred("TIMEOUT", "unknown result", "test");
        QVERIFY(!forget.hasPendingOperation());
        audit.setEvidenceIds({"evd_test"});
        audit.findChild<QPushButton *>("auditExtract")->click();
        QVERIFY(audit.hasPendingOperation());
        QTimer::singleShot(0, &host, [&]() { host.findChild<QMessageBox *>()->accept(); });
        QVERIFY(!host.close());
        emit auditTransport.errorOccurred("TIMEOUT", "unknown result", "test");
        QVERIFY(host.close());
    }
    void editingPreservesFullBodyAndRequiresVersion()
    {
        Transport transport;
        pixiu::MemoryEditDialog editor(nullptr, &transport);
        auto *title = editor.findChild<QLineEdit *>("editTitle");
        auto *body = editor.findChild<QPlainTextEdit *>("editBody");
        auto *save = editor.findChild<QPushButton *>("editSave");
        editor.openMemory("knw_example01", "user:local");
        QCOMPARE(transport.editId, QStringLiteral("knw_example01"));
        QCOMPARE(transport.editScope, QStringLiteral("user:local"));
        QVERIFY(!save->isEnabled());
        const QJsonObject originalBody{{"text", "full body"}, {"nested", QJsonObject{{"keep", true}}}};
        emit transport.memoryItemResult({{"knowledge_id", "knw_example01"}, {"scope", "user:local"},
            {"version", 7}, {"title", "original"}, {"body", originalBody}});
        QVERIFY(!save->isEnabled());
        title->setText("revised");
        QVERIFY(save->isEnabled());
        save->click();
        QVERIFY(!transport.edited.contains("body")); // Title-only edits leave stored body untouched.
        QCOMPARE(transport.edited.value("expected_version").toInt(), 7);
        const auto first = transport.edited;
        QVERIFY(!save->isEnabled());
        editor.reject();
        QVERIFY(editor.isVisible());
        emit transport.errorOccurred("TIMEOUT", "unknown result", "request");
        QCOMPARE(title->text(), QStringLiteral("revised"));
        save->click();
        QCOMPARE(transport.edited, first);
        emit transport.errorOccurred("VERSION_CONFLICT", "changed", "request");
        QVERIFY(!save->isEnabled());
        QCOMPARE(title->text(), QStringLiteral("revised"));
        QCOMPARE(body->toPlainText(), QStringLiteral("full body"));
        editor.findChild<QCheckBox *>("editStructured")->setChecked(true);
        QVERIFY(body->toPlainText().contains("nested"));
        title->setText("still cannot overwrite");
        QVERIFY(!save->isEnabled());
        QCOMPARE(transport.edits, 2);
    }
    void editorRejectsWrongSnapshotAndValidatesSuccess()
    {
        Transport transport;
        pixiu::MemoryEditDialog editor(nullptr, &transport);
        auto *title = editor.findChild<QLineEdit *>("editTitle");
        auto *body = editor.findChild<QPlainTextEdit *>("editBody");
        auto *save = editor.findChild<QPushButton *>("editSave");
        auto *reload = editor.findChild<QPushButton *>("editReload");
        editor.openMemory("knw_example01", "shared:home");
        QJsonObject snapshot{{"knowledge_id", "knw_wrong001"}, {"scope", "shared:home"},
            {"version", 1}, {"title", "original"}, {"body", QJsonObject{{"text", "before"}}}};
        emit transport.memoryItemResult(snapshot);
        QVERIFY(!save->isEnabled());
        QVERIFY(!title->isEnabled());
        reload->click();
        snapshot.insert("knowledge_id", "knw_example01");
        emit transport.memoryItemResult(snapshot);
        title->setText("revised");
        editor.findChild<QCheckBox *>("editStructured")->setChecked(true);
        body->setPlainText("not json");
        QVERIFY(!save->isEnabled());
        body->setPlainText("[]");
        QVERIFY(!save->isEnabled());
        body->setPlainText("{\"text\":\"after\"}");
        QSignalSpy updated(&editor, &pixiu::MemoryEditDialog::memoryUpdated);
        save->click();
        QCOMPARE(transport.edited.value("scope").toString(), QStringLiteral("shared:home"));
        emit transport.memoryUpdated({{"knowledge_id", "knw_wrong001"}, {"version", 2}, {"status", "updated"}, {"evidence_id", "evd_example01"}});
        QCOMPARE(updated.count(), 0);
        QVERIFY(save->isEnabled());
        save->click();
        emit transport.memoryUpdated({{"knowledge_id", "knw_example01"}, {"version", 2}, {"status", "updated"}, {"evidence_id", "evd_example01"}});
        QCOMPARE(updated.count(), 1);
        QVERIFY(!save->isEnabled());
    }
    void plainEditingPreservesFieldsAndProtectsUnsavedInput()
    {
        Transport transport;
        pixiu::MemoryEditDialog editor(nullptr, &transport);
        editor.openMemory("knw_example01", "user:local");
        auto *body = editor.findChild<QPlainTextEdit *>("editBody");
        auto *advanced = editor.findChild<QCheckBox *>("editStructured");
        auto *save = editor.findChild<QPushButton *>("editSave");
        emit transport.memoryItemResult({{"knowledge_id", "knw_example01"}, {"scope", "user:local"},
            {"version", 3}, {"title", "example"}, {"body", QJsonObject{{"text", "before"},
                {"metadata", QJsonObject{{"keep", true}}}}}});
        QCOMPARE(body->toPlainText(), QStringLiteral("before"));
        QVERIFY(!advanced->isChecked());
        advanced->setChecked(true);
        advanced->setChecked(false);
        QVERIFY(!save->isEnabled()); // Merely switching view does not edit the record.
        body->setPlainText("after {not JSON}\n第二行");
        bool defaultCancel = false;
        QTimer::singleShot(0, &editor, [&]() {
            if (auto *question = editor.findChild<QMessageBox *>()) {
                defaultCancel = question->defaultButton() == question->button(QMessageBox::No);
                question->done(QMessageBox::No);
            }
        });
        editor.reject();
        QVERIFY(defaultCancel);
        QVERIFY(editor.isVisible());
        QCOMPARE(body->toPlainText(), QStringLiteral("after {not JSON}\n第二行"));
        advanced->setChecked(true);
        body->setPlainText("invalid JSON");
        advanced->setChecked(false);
        QVERIFY(advanced->isChecked());
        QCOMPARE(body->toPlainText(), QStringLiteral("invalid JSON"));
        QVERIFY(!save->isEnabled());
        body->setPlainText("{\"text\":\"after\",\"metadata\":{\"keep\":true,\"added\":5}}");
        advanced->setChecked(false);
        QCOMPARE(body->toPlainText(), QStringLiteral("after"));
        body->setPlainText("final");
        save->click();
        QCOMPARE(transport.edited.value("body").toObject(), QJsonObject({{"text", "final"},
            {"metadata", QJsonObject{{"keep", true}, {"added", 5}}}}));
        QVERIFY(!transport.edited.contains("title"));
        emit transport.memoryUpdated({{"knowledge_id", "knw_example01"}, {"status", "updated"},
            {"version", 4}, {"evidence_id", "evd_example01"}});
        editor.reject(); // Confirmed saved input requires no discard prompt.
        QVERIFY(!editor.isVisible());
    }
    void settingsOwnPrivacyAndUpgradeOutsideMemory()
    {
        QWidget host;
        pixiu::SettingsWorkspace settings(&host);
        pixiu::MemoryWorkspace memory(&host);
        QVERIFY(!settings.isWindow());
        QVERIFY(settings.findChild<pixiu::PrivacyPage *>());
        QVERIFY(settings.findChild<pixiu::ServiceStatusPage *>());
        QVERIFY(settings.findChild<QPushButton *>("productUpdates"));
        QVERIFY(!memory.findChild<pixiu::PrivacyPage *>());
        QVERIFY(!memory.findChild<pixiu::DevicePage *>());
        QVERIFY(!memory.findChild<QPushButton *>("productUpdates"));
        QSignalSpy requested(&settings, &pixiu::SettingsWorkspace::agentSettingsRequested);
        settings.findChild<QPushButton *>("agentSettings")->click();
        QCOMPARE(requested.count(), 1);
    }
    void forgettingRequiresFreshScopedPreview()
    {
        Transport transport;
        pixiu::ForgetPage page(nullptr, &transport);
        auto *command = page.findChild<QLineEdit *>("forgetCommand");
        auto *preview = page.findChild<QPushButton *>("forgetPreview");
        auto *confirm = page.findChild<QPushButton *>("forgetConfirm");
        QVERIFY(!confirm->isEnabled());
        command->setText("forget example");
        preview->click();
        QVERIFY(!transport.forgetPayload.value("confirm").toBool());
        QCOMPARE(transport.forgetPayload.value("scope").toString(), QStringLiteral("user:local"));
        const QJsonObject response{{"targets", QJsonArray{QJsonObject{{"id", "k1"}, {"version", 1},
            {"title", "Example"}, {"scope", "user:local"}}}}, {"confirmation_token", "token"}, {"expires_in_seconds", 120}};
        emit transport.forgetResult(response);
        QVERIFY(confirm->isEnabled());
        command->setText("changed");
        QVERIFY(!confirm->isEnabled());
        preview->click();
        emit transport.forgetResult(response);
        QVERIFY(QMetaObject::invokeMethod(page.findChild<QTimer *>("forgetExpiry"), "timeout", Qt::DirectConnection));
        QVERIFY(!confirm->isEnabled());
        preview->click();
        emit transport.forgetResult(response);
        page.findChild<QPushButton *>("forgetCancel")->click();
        QVERIFY(!confirm->isEnabled());
        QCOMPARE(transport.forgetCalls, 3);
        preview->click();
        emit transport.forgetResult(response);
        confirm->click();
        QVERIFY(transport.forgetPayload.value("confirm").toBool());
        QCOMPARE(transport.forgetPayload.value("confirmation_token").toString(), QStringLiteral("token"));
        QVERIFY(!confirm->isEnabled());
        emit transport.errorOccurred("TIMEOUT", "offline", "");
        QVERIFY(!confirm->isEnabled());
        QVERIFY(preview->isEnabled());
        preview->click();
        emit transport.forgetResult(response);
        confirm->click();
        QSignalSpy forgotten(&page, &pixiu::ForgetPage::memoryForgotten);
        emit transport.forgetResult({{"status", "forgotten"}, {"forgotten_ids", QJsonArray{"k1"}}});
        QCOMPARE(forgotten.count(), 1);
    }
    void deliveryDistinguishesErrorsAndSupportsSearch()
    {
        Transport transport;
        pixiu::DeliveryPage page(nullptr, &transport);
        auto *insights = page.findChild<QPushButton *>("deliveryInsights");
        auto *digest = page.findChild<QPushButton *>("deliveryDigest");
        auto *date = page.findChild<QDateEdit *>("deliveryDate");
        QVERIFY(date);
        QCOMPARE(date->date(), QDate::currentDate());
        date->setDate(QDate(2026, 9, 7));
        auto *search = page.findChild<QPushButton *>("deliverySearch");
        auto *items = page.findChild<QListWidget *>("deliveryItems");
        auto *status = page.findChild<QLabel *>("deliveryStatus");
        QVERIFY(!search->isEnabled());
        insights->click();
        QVERIFY(!digest->isEnabled());
        QVERIFY(!date->isEnabled());
        emit transport.insightsResult({});
        QVERIFY(status->text().contains("不代表记忆库为空"));
        insights->click();
        emit transport.insightsResult({QJsonObject{{"title", "Example"}, {"summary", "Summary"}, {"knowledge_id", "k1"}, {"score", 0.7}}});
        items->setCurrentRow(0);
        QSignalSpy requested(&page, &pixiu::DeliveryPage::searchRequested);
        search->click();
        QCOMPARE(requested.count(), 1);
        QCOMPARE(requested.at(0).at(0).toString(), QStringLiteral("Example"));
        digest->click();
        QCOMPARE(transport.digestDate, QStringLiteral("2026-09-07"));
        QVERIFY(!date->isEnabled());
        emit transport.errorOccurred("TIMEOUT", "offline", "");
        QVERIFY(status->text().contains("offline"));
        digest->click();
        emit transport.digestResult({{"date", "invalid"}, {"summary", "bad"}});
        QVERIFY(page.findChild<QPlainTextEdit *>("deliveryBody")->toPlainText().isEmpty());
        digest->click();
        emit transport.digestResult({{"date", "2026-09-07"}, {"summary", "当日无新记忆"}});
        QVERIFY(page.findChild<QPlainTextEdit *>("deliveryBody")->toPlainText().contains("当日无新记忆"));
        QVERIFY(date->isEnabled());
        date->setDate(QDate(2024, 2, 29));
        auto *body = page.findChild<QPlainTextEdit *>("deliveryBody");
        QVERIFY(body->toPlainText().isEmpty());
        digest->click();
        QCOMPARE(transport.digestDate, QStringLiteral("2024-02-29"));
        emit transport.digestResult({{"date", "2026-09-07"}, {"summary", "不应显示的旧日摘要"}});
        QVERIFY(body->toPlainText().isEmpty());
        QVERIFY(status->text().contains("不一致"));
        digest->click();
        emit transport.digestResult({{"date", "2024-02-29"}, {"summary", "历史采集简报"}});
        QCOMPARE(body->toPlainText(), QStringLiteral("2024-02-29\n历史采集简报"));
        digest->click();
        QVERIFY(body->toPlainText().isEmpty());
        emit transport.errorOccurred("TIMEOUT", "offline", "");
        emit transport.digestResult({{"date", "2024-02-29"}, {"summary", "过期响应"}});
        QVERIFY(body->toPlainText().isEmpty());
    }
    void leavingNetworkSerializesAndVerifies()
    {
        Transport transport;
        pixiu::DevicePage page(nullptr, &transport);
        auto *leave = page.findChild<QPushButton *>("deviceLeave");
        auto *status = page.findChild<QLabel *>("deviceStatus");
        const QJsonArray peers{QJsonObject{{"id", "self"}, {"is_self", true}},
            QJsonObject{{"id", "a"}, {"is_self", false}}, QJsonObject{{"id", "b"}, {"is_self", false}}};
        leave->click();
        QVERIFY(transport.revoked.isEmpty());
        QTimer::singleShot(0, &page, [&page]() { page.findChild<QMessageBox *>()->done(QMessageBox::No); });
        emit transport.peersResult({{"peers", peers}});
        QVERIFY(transport.revoked.isEmpty());
        QVERIFY(transport.syncSettings.isEmpty());
        leave->click();
        QTimer::singleShot(0, &page, [&page]() { page.findChild<QMessageBox *>()->done(QMessageBox::Yes); });
        emit transport.peersResult({{"peers", peers}});
        QCOMPARE(transport.revoked, QStringLiteral("a"));
        QVERIFY(!leave->isEnabled());
        emit transport.revokeResult({{"status", "revoked"}, {"peer_id", "a"}});
        QCOMPARE(transport.revoked, QStringLiteral("b"));
        QVERIFY(transport.syncSettings.isEmpty());
        emit transport.errorOccurred("TIMEOUT", "offline", "");
        QVERIFY(status->text().contains("退出未完成"));
        QVERIFY(transport.syncSettings.isEmpty());
        QVERIFY(leave->isEnabled());
        leave->click();
        QTimer::singleShot(0, &page, [&page]() { page.findChild<QMessageBox *>()->done(QMessageBox::Yes); });
        emit transport.peersResult({{"peers", QJsonArray{peers.at(0), peers.at(2)}}});
        emit transport.revokeResult({{"status", "revoked"}, {"peer_id", "b"}});
        QVERIFY(!transport.syncSettings.value("enabled").toBool(true));
        emit transport.settingsResult({{"enabled", false}, {"paused", false}});
        QVERIFY(!leave->isEnabled());
        emit transport.peersResult({{"peers", QJsonArray{peers.at(0)}}});
        QVERIFY(status->text().contains("无剩余信任节点"));
        QVERIFY(leave->isEnabled());
    }
    void pairingQrIsClearedAndOversizeFallsBackToText()
    {
        Transport transport;
        pixiu::PairingDialog dialog(nullptr, &transport);
        auto *method = dialog.findChild<QComboBox *>("pairingMethod");
        auto *generate = dialog.findChild<QPushButton *>("pairingGenerate");
        auto *qr = dialog.findChild<QLabel *>("pairingQrImage");
        auto *token = dialog.findChild<QPlainTextEdit *>("pairingLocalToken");
        auto issue = [&](const QString &value) {
            generate->click();
            QVERIFY(qr->pixmap(Qt::ReturnByValue).isNull());
            emit transport.pairingTokenResult({{"token", value}, {"method", "QR"}, {"ttl_seconds", 300}});
        };
        method->setCurrentIndex(1);
        issue("synthetic-qr-test-token");
        QVERIFY(!qr->pixmap(Qt::ReturnByValue).isNull());
        const auto bitmap = qr->pixmap(Qt::ReturnByValue).toImage();
        QVERIFY(bitmap.width() <= 240);
        QCOMPARE(bitmap.pixelColor(0, 0), QColor(Qt::white));
        QMetaObject::invokeMethod(dialog.findChild<QTimer *>("pairingExpiry"), "timeout");
        QVERIFY(qr->pixmap(Qt::ReturnByValue).isNull());
        QVERIFY(token->toPlainText().isEmpty());
        issue(QString(5000, QLatin1Char('x')));
        QVERIFY(qr->pixmap(Qt::ReturnByValue).isNull());
        QCOMPARE(token->toPlainText().size(), 5000);
        issue("another-synthetic-token");
        method->setCurrentIndex(0);
        QVERIFY(qr->pixmap(Qt::ReturnByValue).isNull());
        method->setCurrentIndex(1);
        issue("closing-synthetic-token");
        dialog.reject();
        QVERIFY(qr->pixmap(Qt::ReturnByValue).isNull());
        QVERIFY(token->toPlainText().isEmpty());
    }
    void pairingMatchesMethodsAndPreservesFailedInput()
    {
        Transport transport;
        pixiu::PairingDialog dialog(nullptr, &transport);
        auto *method = dialog.findChild<QComboBox *>("pairingMethod");
        auto *localPin = dialog.findChild<QLineEdit *>("pairingLocalPin");
        auto *remotePin = dialog.findChild<QLineEdit *>("pairingRemotePin");
        auto *localToken = dialog.findChild<QPlainTextEdit *>("pairingLocalToken");
        auto *remoteToken = dialog.findChild<QPlainTextEdit *>("pairingRemoteToken");
        auto *generate = dialog.findChild<QPushButton *>("pairingGenerate");
        auto *submit = dialog.findChild<QPushButton *>("pairingSubmit");
        QVERIFY(!generate->isEnabled());
        localPin->setText("012345");
        generate->click();
        QCOMPARE(transport.tokenRequest.value("method").toString(), QStringLiteral("PIN"));
        QCOMPARE(transport.tokenRequest.value("pin").toString(), QStringLiteral("012345"));
        QVERIFY(!method->isEnabled());
        emit transport.pairingTokenResult({{"token", "local-token"}, {"method", "PIN"}, {"ttl_seconds", 300}});
        QCOMPARE(localToken->toPlainText(), QStringLiteral("local-token"));
        auto *expiry = dialog.findChild<QTimer *>("pairingExpiry");
        QVERIFY(expiry->isActive());
        QVERIFY(QMetaObject::invokeMethod(expiry, "timeout", Qt::DirectConnection));
        QVERIFY(localToken->toPlainText().isEmpty());
        remoteToken->setPlainText("remote-token");
        QVERIFY(!submit->isEnabled());
        remotePin->setText("654321");
        submit->click();
        QCOMPARE(transport.pairCalls, 1);
        QCOMPARE(transport.pairRequest.value("pin").toString(), QStringLiteral("654321"));
        submit->click();
        QCOMPARE(transport.pairCalls, 1);
        dialog.reject();
        QCOMPARE(remoteToken->toPlainText(), QStringLiteral("remote-token"));
        emit transport.errorOccurred("PAIRING_FAILED", "expired", "");
        QCOMPARE(remoteToken->toPlainText(), QStringLiteral("remote-token"));
        QVERIFY(submit->isEnabled());
        method->setCurrentIndex(1);
        QVERIFY(!remotePin->isEnabled());
        generate->click();
        QCOMPARE(transport.tokenRequest.value("method").toString(), QStringLiteral("QR"));
        QVERIFY(!transport.tokenRequest.contains("pin"));
        emit transport.pairingTokenResult({{"token", "wrong-method"}, {"method", "PIN"}, {"ttl_seconds", 300}});
        QVERIFY(localToken->toPlainText().isEmpty());
        submit->click();
        QCOMPARE(transport.pairRequest.value("method").toString(), QStringLiteral("QR"));
        QVERIFY(!transport.pairRequest.contains("pin"));
        QSignalSpy trusted(&dialog, &pixiu::PairingDialog::localTrustEstablished);
        emit transport.pairResult({{"status", "paired"}});
        QCOMPARE(trusted.count(), 0);
        QCOMPARE(remoteToken->toPlainText(), QStringLiteral("remote-token"));
        submit->click();
        emit transport.pairResult({{"status", "paired"}, {"peer_id", "example"}, {"domain", "shared:home"}});
        QCOMPARE(trusted.count(), 1);
        QVERIFY(remoteToken->toPlainText().isEmpty());
        QVERIFY(dialog.findChild<QLabel *>("pairingStatus")->text().contains("实际传输尚未验证"));
        localPin->setText("123456");
        dialog.reject();
        QVERIFY(localPin->text().isEmpty());
        QVERIFY(remotePin->text().isEmpty());
    }
    void deviceSettingsAndTrustRequireEvidence()
    {
        Transport transport;
        pixiu::DevicePage page(nullptr, &transport);
        auto *save = page.findChild<QPushButton *>("deviceSave");
        auto *refresh = page.findChild<QPushButton *>("deviceRefresh");
        auto *revoke = page.findChild<QPushButton *>("deviceRevoke");
        auto *peers = page.findChild<QListWidget *>("devicePeers");
        auto *status = page.findChild<QLabel *>("deviceStatus");
        QVERIFY(!save->isEnabled());
        refresh->click();
        QCOMPARE(transport.statusReads, 1);
        emit transport.syncStatusResult({{"enabled", true}});
        QVERIFY(!save->isEnabled());
        QVERIFY(status->text().contains("不完整"));
        refresh->click();
        emit transport.syncStatusResult({{"enabled", true}, {"paused", false}, {"domain", "shared:home"},
            {"peers_total", 2}, {"pending_outgoing_ops", 1}, {"total_ops_synced", 3}});
        QCOMPARE(transport.peerReads, 1);
        QVERIFY(!save->isEnabled());
        emit transport.peersResult({{"peers", QJsonArray{
            QJsonObject{{"id", "self"}, {"name", "This device"}, {"is_self", true}, {"status", "ONLINE"}},
            QJsonObject{{"id", "peer"}, {"name", "Example peer"}, {"is_self", false}, {"status", "OFFLINE"}}}}});
        QCOMPARE(peers->count(), 2);
        QVERIFY(save->isEnabled());
        peers->setCurrentRow(0);
        QVERIFY(!revoke->isEnabled());
        peers->setCurrentRow(1);
        QVERIFY(revoke->isEnabled());
        QTimer::singleShot(0, &page, [&page]() {
            auto *box = page.findChild<QMessageBox *>();
            QVERIFY(box);
            QCOMPARE(box->defaultButton(), box->button(QMessageBox::No));
            box->done(QMessageBox::No);
        });
        revoke->click();
        QVERIFY(transport.revoked.isEmpty());
        QTimer::singleShot(0, &page, [&page]() { page.findChild<QMessageBox *>()->done(QMessageBox::Yes); });
        revoke->click();
        QCOMPARE(transport.revoked, QStringLiteral("peer"));
        QVERIFY(!revoke->isEnabled());
        emit transport.revokeResult({{"status", "revoked"}, {"peer_id", "wrong-peer"}});
        QVERIFY(status->text().contains("不匹配"));
        QCOMPARE(peers->count(), 2);
        page.findChild<QCheckBox *>("devicePaused")->setChecked(true);
        save->click();
        QVERIFY(transport.syncSettings.value("paused").toBool());
        emit transport.errorOccurred("TIMEOUT", "offline", "");
        QVERIFY(!save->isEnabled());
        QVERIFY(page.findChild<QCheckBox *>("devicePaused")->isChecked());
        QVERIFY(refresh->isEnabled());
    }
    void deviceDiscoveryDistinguishesEmptyAndInvalid()
    {
        Transport transport;
        pixiu::DevicePage page(nullptr, &transport);
        auto *discover = page.findChild<QPushButton *>("deviceDiscover");
        auto *records = page.findChild<QListWidget *>("deviceDiscovered");
        auto *status = page.findChild<QLabel *>("deviceStatus");
        discover->click();
        QCOMPARE(transport.discoveries, 1);
        QVERIFY(!discover->isEnabled());
        emit transport.devicesLoaded({{"devices", QJsonArray{}}});
        QVERIFY(status->text().contains("服务也可能未运行"));
        discover->click();
        emit transport.devicesLoaded({{"status", "not_implemented"}});
        QVERIFY(status->text().contains("不完整"));
        discover->click();
        emit transport.devicesLoaded({{"devices", QJsonArray{QJsonObject{
            {"device_id", "example"}, {"device_name", "Example"}, {"paired", false}}}}});
        QCOMPARE(records->count(), 1);
        QVERIFY(records->item(0)->text().contains("尚无本地信任"));
        QVERIFY(status->text().contains("不代表"));
    }
    void privacyPreservesUnavailableSourcesAndFailedEdits()
    {
        Transport transport;
        pixiu::PrivacyPage page(nullptr, &transport);
        auto *save = page.findChild<QPushButton *>("privacySave");
        auto *load = page.findChild<QPushButton *>("privacyLoad");
        auto *paths = page.findChild<QPlainTextEdit *>("privacyDirectories");
        QVERIFY(!save->isEnabled());
        load->click();
        QCOMPARE(transport.configReads, 1);
        const QJsonObject sources{{"directory", false}, {"behavior", false}, {"clipboard", true}, {"screenshot", false}};
        emit transport.configResult({{"enabled", false}, {"sources", sources}, {"directories", QJsonArray{}}});
        QVERIFY(save->isEnabled());
        paths->setPlainText("relative/path");
        save->click();
        QCOMPARE(transport.configWrites, 0);
        paths->setPlainText("/documents\n/documents\n");
        page.findChild<QCheckBox *>("privacyEnabled")->setChecked(true);
        page.findChild<QCheckBox *>("privacyDirectory")->setChecked(true);
        save->click();
        QCOMPARE(transport.configWrites, 1);
        QCOMPARE(transport.savedConfig.value("directories").toArray(), QJsonArray{"/documents"});
        QVERIFY(transport.savedConfig.value("sources").toObject().value("clipboard").toBool());
        QVERIFY(transport.savedConfig.value("enabled").toBool());
        emit transport.errorOccurred("NETWORK_ERROR", "offline", "");
        QCOMPARE(paths->toPlainText(), QStringLiteral("/documents\n/documents\n"));
        QVERIFY(save->isEnabled());
        page.findChild<QPushButton *>("privacyLogs")->click();
        QCOMPARE(transport.logOffset, 0);
        emit transport.monitorLogResult({QJsonObject{{"source", "directory"}, {"status", "ingested"}, {"summary", "example"}}});
        QCOMPARE(page.findChild<QListWidget *>("privacyEvents")->count(), 1);
    }
    void auditHistoryExtractionAndErrors()
    {
        Transport transport;
        pixiu::MemoryAudit audit(nullptr, &transport);
        auto *refresh = audit.findChild<QPushButton *>("auditRefresh");
        auto *extract = audit.findChild<QPushButton *>("auditExtract");
        auto *records = audit.findChild<QListWidget *>("auditRecords");
        QVERIFY(!extract->isEnabled());
        refresh->click();
        QVERIFY(!refresh->isEnabled());
        emit transport.preferencesListResult({QJsonObject{{"id", "p1"}, {"key", "color"}, {"value", "blue"}}});
        QCOMPARE(records->count(), 1);
        records->setCurrentRow(0);
        QCOMPARE(transport.historyId, QStringLiteral("p1"));
        emit transport.preferenceHistoryResult({{"id", "p1"}, {"key", "color"}, {"current_version", 2},
            {"history", QJsonArray{QJsonObject{{"version", 1}, {"value", "green"}, {"updated_at", 1700000000}}}}});
        QVERIFY(audit.findChild<QPlainTextEdit *>("auditDetails")->toPlainText().contains("green"));
        audit.setEvidenceIds({"e1", "e1", ""});
        extract->click();
        QCOMPARE(transport.extraction.value("evidence_ids").toArray(), QJsonArray{"e1"});
        emit transport.preferenceExtractResult({{"extracted_preferences", QJsonArray{}}});
        QVERIFY(extract->isEnabled());
        audit.findChild<QComboBox *>("auditMode")->setCurrentIndex(1);
        QCOMPARE(transport.conflictRequests, 1);
        emit transport.errorOccurred("NETWORK_ERROR", "offline", "");
        QVERIFY(audit.findChild<QLabel *>("auditStatus")->text().contains("offline"));
        QVERIFY(refresh->isEnabled());
        refresh->click();
        emit transport.conflictsResult({QJsonObject{{"field", "name"}, {"old_value", "old"}, {"new_value", "new"}, {"resolution", "kept"}}});
        records->setCurrentRow(0);
        QVERIFY(audit.findChild<QPlainTextEdit *>("auditDetails")->toPlainText().contains("old"));
        QVERIFY(!extract->isEnabled());
    }
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
        auto *rawToggle = workspace.findChild<QCheckBox *>("memoryEvidenceRaw");
        auto *detail = workspace.findChild<QPlainTextEdit *>("memoryEvidence");
        QVERIFY(rawToggle->isEnabled());
        QVERIFY(!rawToggle->isChecked());
        rawToggle->setChecked(true);
        QVERIFY(detail->toPlainText().contains("\"text\""));
        rawToggle->setChecked(false);
        QCOMPARE(detail->toPlainText(), QStringLiteral("结构化正文"));
        rawToggle->setChecked(true);
        sources->setCurrentRow(-1);
        sources->setCurrentRow(0);
        QVERIFY(!rawToggle->isEnabled());
        QVERIFY(!rawToggle->isChecked());
        QVERIFY(detail->toPlainText().isEmpty());
        emit transport.evidenceDetailResult({{"id", "e1"}, {"raw", QJsonObject{
            {"body", QJsonObject{{"amount", 42}, {"items", QJsonArray{"receipt"}}}}}}});
        QVERIFY(detail->toPlainText().contains("receipt"));
        QVERIFY(detail->toPlainText().contains(QStringLiteral("amount：42")));
        QVERIFY(!rawToggle->isChecked());
        rawToggle->setChecked(true);
        QVERIFY(detail->toPlainText().contains("receipt"));
        workspace.findChild<QComboBox *>("memoryScope")->setCurrentIndex(2);
        QVERIFY(detail->toPlainText().isEmpty());
        QVERIFY(!rawToggle->isEnabled());
    }
    void structuredEvidenceKeepsTextAndAdditionalFields()
    {
        Transport transport;
        pixiu::MemoryWorkspace workspace(nullptr, &transport);
        workspace.findChild<QLineEdit *>("memoryQuery")->setText("test");
        workspace.findChild<QPushButton *>("memorySearch")->click();
        emit transport.queryResult(transport.sequence,
            {{"answer", "test"}, {"source_evidence", QJsonArray{"e1"}}});
        workspace.findChild<QListWidget *>("memorySources")->setCurrentRow(0);
        emit transport.evidenceDetailResult({{"id", "e1"}, {"raw", QJsonObject{
            {"body", QJsonObject{{"text", "<b>literal text</b>"}, {"amount", 0},
                {"approved", false}, {"missing", QJsonValue::Null},
                {"items", QJsonArray{QJsonObject{{"name", "receipt"}}}}}},
            {"tool_name", "calculator"}}}});
        auto *detail = workspace.findChild<QPlainTextEdit *>("memoryEvidence");
        const QString content = detail->toPlainText();
        QVERIFY(content.startsWith("<b>literal text</b>"));
        QVERIFY(content.contains(QStringLiteral("amount：0")));
        QVERIFY(content.contains("false"));
        QVERIFY(content.contains("null"));
        QVERIFY(content.contains("receipt"));
        QVERIFY(content.contains("calculator"));
        QVERIFY(detail->isReadOnly());
        auto *raw = workspace.findChild<QCheckBox *>("memoryEvidenceRaw");
        raw->setChecked(true);
        QVERIFY(detail->toPlainText().contains("\"tool_name\""));
        raw->setChecked(false);
        QCOMPARE(detail->toPlainText(), content);
    }
    void structuredEvidenceBoundsExpansionAndKeepsCompleteRaw()
    {
        Transport transport;
        pixiu::MemoryWorkspace workspace(nullptr, &transport);
        workspace.findChild<QLineEdit *>("memoryQuery")->setText("test");
        workspace.findChild<QPushButton *>("memorySearch")->click();
        emit transport.queryResult(transport.sequence,
            {{"answer", "test"}, {"source_evidence", QJsonArray{"e1"}}});
        auto *sources = workspace.findChild<QListWidget *>("memorySources");
        auto *detail = workspace.findChild<QPlainTextEdit *>("memoryEvidence");
        auto *toggle = workspace.findChild<QCheckBox *>("memoryEvidenceRaw");
        QJsonArray many;
        for (int i = 0; i < 300; ++i) many.append(QString::number(i));
        many.append("last-marker");
        QJsonObject nested{{"leaf", "last-marker"}};
        for (int i = 0; i < 12; ++i) nested = QJsonObject{{"child", nested}};
        const QList<QJsonValue> largeValues{many, nested,
            QString(70000, QLatin1Char('x')) + "last-marker"};
        for (const auto &value : largeValues) {
            sources->setCurrentRow(-1);
            sources->setCurrentRow(0);
            emit transport.evidenceDetailResult({{"id", "e1"},
                {"raw", QJsonObject{{"body", value}}}});
            QVERIFY(!toggle->isChecked());
            QVERIFY(detail->toPlainText().contains(QStringLiteral("完整内容见高级原始数据")));
            QVERIFY(detail->toPlainText().size() < 66000);
            QVERIFY(!detail->toPlainText().contains("last-marker"));
            toggle->setChecked(true);
            QVERIFY(detail->toPlainText().contains("last-marker"));
        }
        sources->setCurrentRow(-1);
        sources->setCurrentRow(0);
        emit transport.evidenceDetailResult({{"id", "e1"}, {"raw", QJsonObject{
            {"text", "  fallback text"}, {"body", QJsonArray{false, QJsonValue::Null, QJsonObject{}}}}}});
        QVERIFY(detail->toPlainText().startsWith("  fallback text"));
        QVERIFY(detail->toPlainText().contains("false"));
        QVERIFY(detail->toPlainText().contains("null"));
        QVERIFY(detail->toPlainText().contains(QStringLiteral("空对象")));
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
