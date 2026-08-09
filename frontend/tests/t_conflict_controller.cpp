#include <QJsonArray>
#include <QJsonObject>
#include <QSignalSpy>
#include <QTest>

#include "app/ConflictController.h"
#include "services/BackendTransport.h"

// 测试替身：记录 listConflicts 调用并可由测试主动发射结果信号。
class FakeTransport : public BackendTransport
{
public:
    void connectToBackend() override {}
    void disconnectFromBackend() override {}
    quint64 queryMemory(const QString &, const QJsonObject &) override { return 0; }
    void writeMemory(const QJsonObject &) override {}
    void forget(const QString &, bool) override {}
    void listConflicts() override { ++listConflictsCalls; }
    void preferenceHistory(const QString &) override {}
    void promoteMemory(const QJsonObject &) override {}
    void pairDevice(const QJsonObject &) override {}
    void listPeers() override {}
    void syncStatus() override {}
    void revokePeer(const QString &) override {}
    ConnectionState connectionState() const override { return ConnectionState::Connected; }
    QString baseUrl() const override { return QStringLiteral("http://127.0.0.1:8765"); }

    int listConflictsCalls = 0;
};

// ConflictController 加载与结果上抛契约测试。
class TestConflictController : public QObject
{
    Q_OBJECT

private slots:
    void refreshRequestsConflicts();
    void refreshWhileInFlightIsIgnored();
    void conflictsAreForwarded();
    void staleResultsAreIgnored();
    void errorsAreForwarded();
};

void TestConflictController::refreshRequestsConflicts()
{
    FakeTransport transport;
    ConflictController controller(&transport);
    controller.refresh();
    QCOMPARE(transport.listConflictsCalls, 1);
}

void TestConflictController::refreshWhileInFlightIsIgnored()
{
    FakeTransport transport;
    ConflictController controller(&transport);

    controller.refresh();
    controller.refresh();
    QCOMPARE(transport.listConflictsCalls, 1);

    // 在途响应返回后，新的刷新可再次发起。
    emit transport.conflictsResult(QJsonArray());
    controller.refresh();
    QCOMPARE(transport.listConflictsCalls, 2);
}

void TestConflictController::conflictsAreForwarded()
{
    FakeTransport transport;
    ConflictController controller(&transport);
    QSignalSpy loadedSpy(&controller, &ConflictController::conflictsLoaded);

    controller.refresh();
    QJsonArray conflicts;
    conflicts.append(QJsonObject{
        {QStringLiteral("knowledge_title"), QStringLiteral("2026年4月家庭支出清单")},
        {QStringLiteral("field"), QStringLiteral("body.items[2].amount")},
        {QStringLiteral("old_value"), 156},
        {QStringLiteral("new_value"), 186},
        {QStringLiteral("resolution"), QStringLiteral("NEW_WINS")},
        {QStringLiteral("created_at"), 1714608000}});
    emit transport.conflictsResult(conflicts);

    QCOMPARE(loadedSpy.count(), 1);
    QCOMPARE(loadedSpy.takeFirst().at(0).toJsonArray().size(), 1);
}

void TestConflictController::staleResultsAreIgnored()
{
    FakeTransport transport;
    ConflictController controller(&transport);
    QSignalSpy loadedSpy(&controller, &ConflictController::conflictsLoaded);

    // 未 refresh 时到达的结果视为过期，不向上抛。
    emit transport.conflictsResult(QJsonArray());
    QCOMPARE(loadedSpy.count(), 0);
}

void TestConflictController::errorsAreForwarded()
{
    FakeTransport transport;
    ConflictController controller(&transport);
    QSignalSpy failedSpy(&controller, &ConflictController::failed);

    controller.refresh();
    emit transport.errorOccurred(QStringLiteral("NETWORK_ERROR"),
                                 QStringLiteral("connection refused"), QString());
    QCOMPARE(failedSpy.count(), 1);
    QCOMPARE(failedSpy.takeFirst().at(0).toString(),
             QStringLiteral("NETWORK_ERROR"));
}

QTEST_MAIN(TestConflictController)
#include "t_conflict_controller.moc"
