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
    void promoteMemory(const QJsonObject &) override {}
    void pairDevice(const QJsonObject &) override {}
    void listPeers() override {}
    void syncStatus() override {}
    void revokePeer(const QString &) override {}
    ConnectionState connectionState() const override { return ConnectionState::Connected; }
    QString baseUrl() const override { return QStringLiteral("http://127.0.0.1:8765"); }

    QString lastPreferenceId;
    int historyCalls = 0;
};

// PreferenceController 加载契约测试。
class TestPreferenceController : public QObject
{
    Q_OBJECT

private slots:
    void loadHistoryRequestsEndpoint();
    void historyIsForwarded();
    void staleResultsAreIgnored();
};

void TestPreferenceController::loadHistoryRequestsEndpoint()
{
    FakeTransport transport;
    PreferenceController controller(&transport);
    controller.loadHistory(QStringLiteral(" pref_abc "));
    QCOMPARE(transport.historyCalls, 1);
    QCOMPARE(transport.lastPreferenceId, QStringLiteral("pref_abc"));
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

QTEST_MAIN(TestPreferenceController)
#include "t_preference_controller.moc"
