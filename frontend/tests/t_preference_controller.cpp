#include <QJsonObject>
#include <QSignalSpy>
#include <QTest>

#include "app/PreferenceController.h"
#include "services/BackendTransport.h"

// 测试替身：记录 preferenceHistory 调用并可由测试主动发射结果信号。
class FakeTransport : public BackendTransport
{
public:
    void connectToBackend() override {}
    void disconnectFromBackend() override {}
    quint64 queryMemory(const QString &, const QJsonObject &) override { return 0; }
    void writeMemory(const QJsonObject &) override {}
    void forget(const QString &, bool) override {}
    void listConflicts() override {}
    void preferenceHistory(const QString &preferenceId) override
    {
        lastPreferenceId = preferenceId;
        ++historyCalls;
    }
    void extractPreferences(const QJsonObject &payload) override
    {
        lastExtractPayload = payload;
        ++extractCalls;
    }
    void promoteMemory(const QJsonObject &) override {}
    void pairDevice(const QJsonObject &) override {}
    void listPeers() override {}
    void syncStatus() override {}
    void revokePeer(const QString &) override {}
    ConnectionState connectionState() const override { return ConnectionState::Connected; }
    QString baseUrl() const override { return QStringLiteral("http://127.0.0.1:8765"); }

    QString lastPreferenceId;
    int historyCalls = 0;
    QJsonObject lastExtractPayload;
    int extractCalls = 0;
};

// PreferenceController 加载契约测试。
class TestPreferenceController : public QObject
{
    Q_OBJECT

private slots:
    void loadHistoryRequestsEndpoint();
    void loadWhilePendingIsIgnored();
    void historyIsForwarded();
    void staleResultsAreIgnored();
    void extractRequestsEndpointWithEvidenceIds();
    void extractEmptyIdsAreIgnored();
    void extractWhilePendingIsIgnored();
    void extractResultIsForwarded();
    void extractErrorIsForwarded();
};

void TestPreferenceController::loadHistoryRequestsEndpoint()
{
    FakeTransport transport;
    PreferenceController controller(&transport);
    controller.loadHistory(QStringLiteral(" pref_abc "));
    QCOMPARE(transport.historyCalls, 1);
    QCOMPARE(transport.lastPreferenceId, QStringLiteral("pref_abc"));
}

void TestPreferenceController::loadWhilePendingIsIgnored()
{
    FakeTransport transport;
    PreferenceController controller(&transport);
    QSignalSpy loadedSpy(&controller, &PreferenceController::historyLoaded);

    controller.loadHistory(QStringLiteral("pref_a"));
    controller.loadHistory(QStringLiteral("pref_b"));
    QCOMPARE(transport.historyCalls, 1);
    QCOMPARE(transport.lastPreferenceId, QStringLiteral("pref_a"));

    // 在途响应正常上抛（不会被误配到被忽略的第二次请求）。
    emit transport.preferenceHistoryResult(
        QJsonObject{{QStringLiteral("id"), QStringLiteral("pref_a")}});
    QCOMPARE(loadedSpy.count(), 1);

    // 完成后新的加载请求放行。
    controller.loadHistory(QStringLiteral("pref_b"));
    QCOMPARE(transport.historyCalls, 2);
    QCOMPARE(transport.lastPreferenceId, QStringLiteral("pref_b"));
}

void TestPreferenceController::historyIsForwarded()
{
    FakeTransport transport;
    PreferenceController controller(&transport);
    QSignalSpy loadedSpy(&controller, &PreferenceController::historyLoaded);

    controller.loadHistory(QStringLiteral("pref_abc"));
    QJsonObject response;
    response.insert(QStringLiteral("id"), QStringLiteral("pref_abc"));
    response.insert(QStringLiteral("current_version"), 2);
    emit transport.preferenceHistoryResult(response);

    QCOMPARE(loadedSpy.count(), 1);
    QCOMPARE(loadedSpy.takeFirst().at(0).toJsonObject()
                 .value(QStringLiteral("current_version")).toInt(),
             2);
}

void TestPreferenceController::staleResultsAreIgnored()
{
    FakeTransport transport;
    PreferenceController controller(&transport);
    QSignalSpy loadedSpy(&controller, &PreferenceController::historyLoaded);

    emit transport.preferenceHistoryResult(QJsonObject());
    QCOMPARE(loadedSpy.count(), 0);
}

void TestPreferenceController::extractRequestsEndpointWithEvidenceIds()
{
    FakeTransport transport;
    PreferenceController controller(&transport);
    controller.extract(QStringList{QStringLiteral("evd_abc"),
                                   QStringLiteral("evd_def")});
    QCOMPARE(transport.extractCalls, 1);
    const QJsonArray ids =
        transport.lastExtractPayload.value(QStringLiteral("evidence_ids"))
            .toArray();
    QCOMPARE(ids.size(), 2);
    QCOMPARE(ids.first().toString(), QStringLiteral("evd_abc"));
}

void TestPreferenceController::extractEmptyIdsAreIgnored()
{
    FakeTransport transport;
    PreferenceController controller(&transport);
    controller.extract(QStringList());
    QCOMPARE(transport.extractCalls, 0);
}

void TestPreferenceController::extractWhilePendingIsIgnored()
{
    FakeTransport transport;
    PreferenceController controller(&transport);
    QSignalSpy extractedSpy(&controller, &PreferenceController::extracted);

    controller.extract(QStringList{QStringLiteral("evd_a")});
    controller.extract(QStringList{QStringLiteral("evd_b")});
    QCOMPARE(transport.extractCalls, 1);

    emit transport.preferenceExtractResult(
        QJsonObject{{QStringLiteral("extracted_preferences"), QJsonArray{}}});
    QCOMPARE(extractedSpy.count(), 1);

    controller.extract(QStringList{QStringLiteral("evd_b")});
    QCOMPARE(transport.extractCalls, 2);
}

void TestPreferenceController::extractResultIsForwarded()
{
    FakeTransport transport;
    PreferenceController controller(&transport);
    QSignalSpy extractedSpy(&controller, &PreferenceController::extracted);

    controller.extract(QStringList{QStringLiteral("evd_abc")});
    emit transport.preferenceExtractResult(
        QJsonObject{
            {QStringLiteral("extracted_preferences"),
             QJsonArray{QJsonObject{{QStringLiteral("id"),
                                     QStringLiteral("pref_x")}},
                        QJsonObject{{QStringLiteral("id"),
                                     QStringLiteral("pref_y")}}}},
            {QStringLiteral("latency_ms"), 15},
        });

    QCOMPARE(extractedSpy.count(), 1);
    const QList<QVariant> args = extractedSpy.takeFirst();
    QCOMPARE(args.at(0).toInt(), 2);
    QCOMPARE(args.at(1).toInt(), 15);
}

void TestPreferenceController::extractErrorIsForwarded()
{
    FakeTransport transport;
    PreferenceController controller(&transport);
    QSignalSpy failedSpy(&controller, &PreferenceController::extractFailed);
    QSignalSpy historyFailedSpy(&controller, &PreferenceController::failed);

    controller.extract(QStringList{QStringLiteral("evd_abc")});
    emit transport.errorOccurred(QStringLiteral("NOT_FOUND"),
                                 QStringLiteral("no such evidence"),
                                 QString());

    QCOMPARE(failedSpy.count(), 1);
    QCOMPARE(failedSpy.takeFirst().at(0).toString(),
             QStringLiteral("NOT_FOUND"));
    QCOMPARE(historyFailedSpy.count(), 0);
}

QTEST_MAIN(TestPreferenceController)
#include "t_preference_controller.moc"
