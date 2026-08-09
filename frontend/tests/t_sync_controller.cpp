#include <QJsonArray>
#include <QJsonObject>
#include <QSignalSpy>
#include <QStringList>
#include <QTest>

#include "app/SyncController.h"
#include "services/BackendTransport.h"

// 测试替身：记录 listPeers / syncStatus / revokePeer 调用，测试可主动发射结果信号。
class FakeTransport : public BackendTransport
{
public:
    void connectToBackend() override {}
    void disconnectFromBackend() override {}
    quint64 queryMemory(const QString &, const QJsonObject &) override { return 0; }
    void writeMemory(const QJsonObject &) override {}
    void forget(const QString &, bool) override {}
    void listConflicts() override {}
    void preferenceHistory(const QString &) override {}
    void promoteMemory(const QJsonObject &) override {}
    void pairDevice(const QJsonObject &) override {}
    void listPeers() override { ++listPeersCalls; }
    void syncStatus() override { ++syncStatusCalls; }
    void revokePeer(const QString &peerId) override { revokePeerCalls.append(peerId); }
    ConnectionState connectionState() const override { return ConnectionState::Connected; }
    QString baseUrl() const override { return QStringLiteral("http://127.0.0.1:8765"); }

    int listPeersCalls = 0;
    int syncStatusCalls = 0;
    QStringList revokePeerCalls;
};

// SyncController：节点列表 / 同步状态 / 解绑的请求与结果契约测试。
class TestSyncController : public QObject
{
    Q_OBJECT

private slots:
    void refreshRequestsPeersAndStatus();
    void peersAreForwarded();
    void peersNotImplementedIsReported();
    void syncStatusIsForwarded();
    void syncStatusNotImplementedIsReported();
    void revokeSendsRequestAndReportsRevoked();
    void revokeNotImplementedIsReported();
    void revokeIgnoresEmptyId();
    void staleResponsesAreIgnored();
    void errorsAreForwarded();
};

void TestSyncController::refreshRequestsPeersAndStatus()
{
    FakeTransport transport;
    SyncController controller(&transport);
    controller.refresh();
    QCOMPARE(transport.listPeersCalls, 1);
    QCOMPARE(transport.syncStatusCalls, 1);
}

void TestSyncController::peersAreForwarded()
{
    FakeTransport transport;
    SyncController controller(&transport);
    QSignalSpy loadedSpy(&controller, &SyncController::peersLoaded);

    controller.refresh();
    QJsonArray peers;
    peers.append(QJsonObject{
        {QStringLiteral("id"), QStringLiteral("dev_self")},
        {QStringLiteral("name"), QStringLiteral("书房工作站")},
        {QStringLiteral("is_self"), true},
        {QStringLiteral("status"), QStringLiteral("ONLINE")}});
    peers.append(QJsonObject{
        {QStringLiteral("id"), QStringLiteral("dev_guest")},
        {QStringLiteral("name"), QStringLiteral("客厅一体机")},
        {QStringLiteral("is_self"), false},
        {QStringLiteral("status"), QStringLiteral("ONLINE")},
        {QStringLiteral("pending_ops"), 3}});
    emit transport.peersResult(QJsonObject{
        {QStringLiteral("peers"), peers}});

    QCOMPARE(loadedSpy.count(), 1);
    QCOMPARE(loadedSpy.takeFirst().at(0).toJsonArray().size(), 2);
}

void TestSyncController::peersNotImplementedIsReported()
{
    FakeTransport transport;
    SyncController controller(&transport);
    QSignalSpy loadedSpy(&controller, &SyncController::peersLoaded);
    QSignalSpy pendingSpy(&controller, &SyncController::notImplemented);

    controller.refresh();
    emit transport.peersResult(QJsonObject{
        {QStringLiteral("status"), QStringLiteral("not_implemented")}});

    QCOMPARE(loadedSpy.count(), 0);
    QCOMPARE(pendingSpy.count(), 1);
    QCOMPARE(pendingSpy.takeFirst().at(0).toString(),
             QStringLiteral("peers"));
}

void TestSyncController::syncStatusIsForwarded()
{
    FakeTransport transport;
    SyncController controller(&transport);
    QSignalSpy loadedSpy(&controller, &SyncController::syncStatusLoaded);

    controller.refresh();
    emit transport.syncStatusResult(QJsonObject{
        {QStringLiteral("domain"), QStringLiteral("shared:home")},
        {QStringLiteral("peers_online"), 2},
        {QStringLiteral("peers_total"), 3},
        {QStringLiteral("pending_outgoing_ops"), 0},
        {QStringLiteral("total_ops_synced"), 1285}});

    QCOMPARE(loadedSpy.count(), 1);
    const QJsonObject status = loadedSpy.takeFirst().at(0).toJsonObject();
    QCOMPARE(status.value(QStringLiteral("domain")).toString(),
             QStringLiteral("shared:home"));
}

void TestSyncController::syncStatusNotImplementedIsReported()
{
    FakeTransport transport;
    SyncController controller(&transport);
    QSignalSpy loadedSpy(&controller, &SyncController::syncStatusLoaded);
    QSignalSpy pendingSpy(&controller, &SyncController::notImplemented);

    controller.refresh();
    emit transport.syncStatusResult(QJsonObject{
        {QStringLiteral("status"), QStringLiteral("not_implemented")}});

    QCOMPARE(loadedSpy.count(), 0);
    QCOMPARE(pendingSpy.count(), 1);
    QCOMPARE(pendingSpy.takeFirst().at(0).toString(),
             QStringLiteral("sync_status"));
}

void TestSyncController::revokeSendsRequestAndReportsRevoked()
{
    FakeTransport transport;
    SyncController controller(&transport);
    QSignalSpy revokedSpy(&controller, &SyncController::revoked);

    controller.revokePeer(QStringLiteral("dev_guest"));
    QCOMPARE(transport.revokePeerCalls.size(), 1);
    QCOMPARE(transport.revokePeerCalls.first(), QStringLiteral("dev_guest"));

    emit transport.revokeResult(QJsonObject{
        {QStringLiteral("status"), QStringLiteral("revoked")},
        {QStringLiteral("peer_id"), QStringLiteral("dev_guest")},
        {QStringLiteral("domain"), QStringLiteral("shared:home")}});

    QCOMPARE(revokedSpy.count(), 1);
    QCOMPARE(revokedSpy.takeFirst().at(0).toString(),
             QStringLiteral("dev_guest"));
}

void TestSyncController::revokeNotImplementedIsReported()
{
    FakeTransport transport;
    SyncController controller(&transport);
    QSignalSpy revokedSpy(&controller, &SyncController::revoked);
    QSignalSpy pendingSpy(&controller, &SyncController::notImplemented);

    controller.revokePeer(QStringLiteral("dev_guest"));
    emit transport.revokeResult(QJsonObject{
        {QStringLiteral("status"), QStringLiteral("not_implemented")}});

    QCOMPARE(revokedSpy.count(), 0);
    QCOMPARE(pendingSpy.count(), 1);
    QCOMPARE(pendingSpy.takeFirst().at(0).toString(),
             QStringLiteral("revoke"));
}

void TestSyncController::revokeIgnoresEmptyId()
{
    FakeTransport transport;
    SyncController controller(&transport);
    controller.revokePeer(QString());
    controller.revokePeer(QStringLiteral("   "));
    QCOMPARE(transport.revokePeerCalls.size(), 0);
}

void TestSyncController::staleResponsesAreIgnored()
{
    FakeTransport transport;
    SyncController controller(&transport);
    QSignalSpy loadedSpy(&controller, &SyncController::peersLoaded);
    QSignalSpy statusSpy(&controller, &SyncController::syncStatusLoaded);

    // 无在途请求时到达的响应视为过期，不向上抛。
    emit transport.peersResult(QJsonObject{
        {QStringLiteral("peers"), QJsonArray()}});
    emit transport.syncStatusResult(QJsonObject{
        {QStringLiteral("domain"), QStringLiteral("shared:home")}});
    QCOMPARE(loadedSpy.count(), 0);
    QCOMPARE(statusSpy.count(), 0);
}

void TestSyncController::errorsAreForwarded()
{
    FakeTransport transport;
    SyncController controller(&transport);
    QSignalSpy failedSpy(&controller, &SyncController::failed);

    controller.refresh();
    emit transport.errorOccurred(QStringLiteral("NETWORK_ERROR"),
                                 QStringLiteral("connection refused"), QString());
    QCOMPARE(failedSpy.count(), 1);
    QCOMPARE(failedSpy.takeFirst().at(0).toString(),
             QStringLiteral("NETWORK_ERROR"));

    // 错误后未再刷新，后续错误与同步管理无关，不应重复上抛。
    emit transport.errorOccurred(QStringLiteral("HTTP_500"),
                                 QStringLiteral("server error"), QString());
    QCOMPARE(failedSpy.count(), 0);
}

QTEST_MAIN(TestSyncController)
#include "t_sync_controller.moc"
