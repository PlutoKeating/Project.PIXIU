#include "MemoryWorkspace.h"
#include "MemoryWriteDialog.h"
#include "MemoryAudit.h"
#include "PrivacyPage.h"
#include "DevicePage.h"
#include "DeliveryPage.h"
#include "ForgetPage.h"
#include "SettingsWorkspace.h"
#include <QTabWidget>
#include "PairingDialog.h"
#include <QMessageBox>
#include <QTimer>
#include <QCheckBox>
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
    QString auditScope, historyId;
    QJsonObject extraction;
    int conflictRequests = 0;
    int statusReads = 0, peerReads = 0, discoveries = 0;
    QJsonObject syncSettings;
    QString revoked;
    QJsonObject tokenRequest, pairRequest;
    int pairCalls = 0;
    int insightReads = 0, digestReads = 0;
    QJsonObject forgetPayload;
    int forgetCalls = 0;
    void reviewedForget(const QJsonObject &payload) override { forgetPayload = payload; ++forgetCalls; }
    void deliveryInsights() override { ++insightReads; }
    void deliveryDigest() override { ++digestReads; }
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
    void settingsOwnPrivacyAndUpgradeOutsideMemory()
    {
        QWidget host;
        pixiu::SettingsWorkspace settings(&host);
        pixiu::MemoryWorkspace memory(&host);
        QVERIFY(!settings.isWindow());
        QVERIFY(settings.findChild<pixiu::PrivacyPage *>());
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
        auto *search = page.findChild<QPushButton *>("deliverySearch");
        auto *items = page.findChild<QListWidget *>("deliveryItems");
        auto *status = page.findChild<QLabel *>("deliveryStatus");
        QVERIFY(!search->isEnabled());
        insights->click();
        QVERIFY(!digest->isEnabled());
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
        emit transport.errorOccurred("TIMEOUT", "offline", "");
        QVERIFY(status->text().contains("offline"));
        digest->click();
        emit transport.digestResult({{"date", "invalid"}, {"summary", "bad"}});
        QVERIFY(page.findChild<QPlainTextEdit *>("deliveryBody")->toPlainText().isEmpty());
        digest->click();
        emit transport.digestResult({{"date", "2026-09-07"}, {"summary", "当日无新记忆"}});
        QVERIFY(page.findChild<QPlainTextEdit *>("deliveryBody")->toPlainText().contains("当日无新记忆"));
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
