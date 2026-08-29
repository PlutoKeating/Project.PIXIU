#include <QJsonArray>
#include <QJsonObject>
#include <QSignalSpy>
#include <QStringList>
#include <QTest>

#include "app/SyncController.h"
#include "services/BackendTransport.h"

// 测试替身：记录 listPeers / syncStatus / revokePeer / discoverDevices /
// requestPairing / confirmPairing / updateSyncSettings 调用，测试可主动发射结果信号。
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
    void discoverDevices() override { ++discoverCalls; }
    void requestPairing(const QString &targetId) override
    {
        requestPairingCalls.append(targetId);
    }
    void confirmPairing(const QString &requestId, bool accept) override
    {
        confirmPairingCalls.append(qMakePair(requestId, accept));
    }
    void updateSyncSettings(bool enabled, bool paused) override
    {
        settingsCalls.append(qMakePair(enabled, paused));
    }
    ConnectionState connectionState() const override { return ConnectionState::Connected; }
    QString baseUrl() const override { return QStringLiteral("http://127.0.0.1:8765"); }

    int listPeersCalls = 0;
    int syncStatusCalls = 0;
    int discoverCalls = 0;
    QStringList revokePeerCalls;
    QStringList requestPairingCalls;
    QList<QPair<QString, bool>> confirmPairingCalls;
    QList<QPair<bool, bool>> settingsCalls;
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
    void discoverRequestsAndForwardsDevices();
    void requestPairingSendsTargetAndForwardsPin();
    void confirmPairingForwardsResult();
    void updateSettingsSendsBothAndForwards();
    void syncNowReusesRefresh();
    void pairingNotImplementedIsReported();
    void newFlowErrorsAreForwarded();
    void newFlowStaleResponsesAreIgnored();
    void pairingFlowsIgnoreEmptyIds();
    void pairConfirmNotImplementedIsReported();
    void settingsNotImplementedIsReported();
    void concurrentErrorClearsAllPendings();
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

void TestSyncController::discoverRequestsAndForwardsDevices()
{
    FakeTransport transport;
    SyncController controller(&transport);
    QSignalSpy loadedSpy(&controller, &SyncController::discoveredDevices);

    controller.discover();
    QCOMPARE(transport.discoverCalls, 1);

    QJsonArray devices;
    devices.append(QJsonObject{
        {QStringLiteral("device_id"), QStringLiteral("dev_guest")},
        {QStringLiteral("device_name"), QStringLiteral("客厅一体机")},
        {QStringLiteral("addresses"), QJsonArray{QStringLiteral("192.168.1.10")}},
        {QStringLiteral("port"), 8766},
        {QStringLiteral("pairable"), true},
        {QStringLiteral("paired"), false}});
    emit transport.devicesLoaded(QJsonObject{
        {QStringLiteral("devices"), devices}});

    QCOMPARE(loadedSpy.count(), 1);
    const QJsonArray result = loadedSpy.takeFirst().at(0).toJsonArray();
    QCOMPARE(result.size(), 1);
    QCOMPARE(result.first().toObject().value(QStringLiteral("device_id")).toString(),
             QStringLiteral("dev_guest"));
    QCOMPARE(result.first().toObject().value(QStringLiteral("pairable")).toBool(),
             true);
}

void TestSyncController::requestPairingSendsTargetAndForwardsPin()
{
    FakeTransport transport;
    SyncController controller(&transport);
    QSignalSpy pairingSpy(&controller, &SyncController::pairRequestResult);

    controller.requestPairing(QStringLiteral("dev_guest"));
    QCOMPARE(transport.requestPairingCalls.size(), 1);
    QCOMPARE(transport.requestPairingCalls.first(), QStringLiteral("dev_guest"));

    emit transport.pairRequestResult(QJsonObject{
        {QStringLiteral("request_id"), QStringLiteral("req_pair1")},
        {QStringLiteral("pin"), QStringLiteral("483920")},
        {QStringLiteral("target_device_id"), QStringLiteral("dev_guest")},
        {QStringLiteral("expires_at"), 1756080060}});

    QCOMPARE(pairingSpy.count(), 1);
    const QJsonObject result = pairingSpy.takeFirst().at(0).toJsonObject();
    QCOMPARE(result.value(QStringLiteral("pin")).toString(),
             QStringLiteral("483920"));
    QCOMPARE(result.value(QStringLiteral("request_id")).toString(),
             QStringLiteral("req_pair1"));
}

void TestSyncController::confirmPairingForwardsResult()
{
    FakeTransport transport;
    SyncController controller(&transport);
    QSignalSpy pairingSpy(&controller, &SyncController::pairConfirmResult);

    // accept=true → accepted。
    controller.confirmPairing(QStringLiteral("req_pair1"), true);
    QCOMPARE(transport.confirmPairingCalls.size(), 1);
    QCOMPARE(transport.confirmPairingCalls.first().first,
             QStringLiteral("req_pair1"));
    QCOMPARE(transport.confirmPairingCalls.first().second, true);
    emit transport.pairConfirmResult(QJsonObject{
        {QStringLiteral("status"), QStringLiteral("accepted")}});
    QCOMPARE(pairingSpy.count(), 1);
    QCOMPARE(pairingSpy.takeFirst().at(0).toJsonObject()
                 .value(QStringLiteral("status")).toString(),
             QStringLiteral("accepted"));

    // accept=false → rejected。
    controller.confirmPairing(QStringLiteral("req_pair2"), false);
    QCOMPARE(transport.confirmPairingCalls.size(), 2);
    QCOMPARE(transport.confirmPairingCalls.at(1).second, false);
    emit transport.pairConfirmResult(QJsonObject{
        {QStringLiteral("status"), QStringLiteral("rejected")}});
    QCOMPARE(pairingSpy.count(), 1);
    QCOMPARE(pairingSpy.takeFirst().at(0).toJsonObject()
                 .value(QStringLiteral("status")).toString(),
             QStringLiteral("rejected"));
}

void TestSyncController::updateSettingsSendsBothAndForwards()
{
    FakeTransport transport;
    SyncController controller(&transport);
    QSignalSpy settingsSpy(&controller, &SyncController::settingsResult);

    controller.updateSettings(false, true);
    QCOMPARE(transport.settingsCalls.size(), 1);
    QCOMPARE(transport.settingsCalls.first().first, false);
    QCOMPARE(transport.settingsCalls.first().second, true);

    emit transport.settingsResult(QJsonObject{
        {QStringLiteral("enabled"), false},
        {QStringLiteral("paused"), true}});

    QCOMPARE(settingsSpy.count(), 1);
    const QJsonObject result = settingsSpy.takeFirst().at(0).toJsonObject();
    QCOMPARE(result.value(QStringLiteral("enabled")).toBool(), false);
    QCOMPARE(result.value(QStringLiteral("paused")).toBool(), true);
}

void TestSyncController::syncNowReusesRefresh()
{
    FakeTransport transport;
    SyncController controller(&transport);

    // 后端无 /sync/now 端点：立即同步复用 refresh（listPeers + syncStatus）。
    controller.syncNow();
    QCOMPARE(transport.listPeersCalls, 1);
    QCOMPARE(transport.syncStatusCalls, 1);
}

void TestSyncController::pairingNotImplementedIsReported()
{
    FakeTransport transport;
    SyncController controller(&transport);
    QSignalSpy pairingSpy(&controller, &SyncController::pairRequestResult);
    QSignalSpy pendingSpy(&controller, &SyncController::notImplemented);

    controller.requestPairing(QStringLiteral("dev_guest"));
    emit transport.pairRequestResult(QJsonObject{
        {QStringLiteral("status"), QStringLiteral("not_implemented")}});

    QCOMPARE(pairingSpy.count(), 0);
    QCOMPARE(pendingSpy.count(), 1);
    QCOMPARE(pendingSpy.takeFirst().at(0).toString(),
             QStringLiteral("pair_request"));
}

void TestSyncController::newFlowErrorsAreForwarded()
{
    FakeTransport transport;
    SyncController controller(&transport);
    QSignalSpy failedSpy(&controller, &SyncController::failed);

    // 发现/配对/设置类在途请求的通用错误统一走 failed，且错误后不重复上抛。
    controller.discover();
    controller.requestPairing(QStringLiteral("dev_guest"));
    emit transport.errorOccurred(QStringLiteral("NETWORK_ERROR"),
                                 QStringLiteral("connection refused"), QString());
    QCOMPARE(failedSpy.count(), 1);
    QCOMPARE(failedSpy.takeFirst().at(0).toString(),
             QStringLiteral("NETWORK_ERROR"));

    emit transport.errorOccurred(QStringLiteral("HTTP_500"),
                                 QStringLiteral("server error"), QString());
    QCOMPARE(failedSpy.count(), 0);
}

void TestSyncController::newFlowStaleResponsesAreIgnored()
{
    FakeTransport transport;
    SyncController controller(&transport);
    QSignalSpy discoverSpy(&controller, &SyncController::discoveredDevices);
    QSignalSpy settingsSpy(&controller, &SyncController::settingsResult);

    // 无在途请求时到达的发现/设置响应视为过期，不向上抛（仿
    // staleResponsesAreIgnored，覆盖新流程的 stale 检查）。
    emit transport.devicesLoaded(QJsonObject{
        {QStringLiteral("devices"), QJsonArray()}});
    emit transport.settingsResult(QJsonObject{
        {QStringLiteral("enabled"), true},
        {QStringLiteral("paused"), false}});
    QCOMPARE(discoverSpy.count(), 0);
    QCOMPARE(settingsSpy.count(), 0);
}

void TestSyncController::pairingFlowsIgnoreEmptyIds()
{
    FakeTransport transport;
    SyncController controller(&transport);

    // 空/空白 id 的配对请求与确认一律忽略（仿 revokeIgnoresEmptyId）。
    controller.requestPairing(QString());
    controller.requestPairing(QStringLiteral("   "));
    controller.confirmPairing(QString(), true);
    controller.confirmPairing(QStringLiteral("   "), false);
    QCOMPARE(transport.requestPairingCalls.size(), 0);
    QCOMPARE(transport.confirmPairingCalls.size(), 0);
}

void TestSyncController::pairConfirmNotImplementedIsReported()
{
    FakeTransport transport;
    SyncController controller(&transport);
    QSignalSpy pairingSpy(&controller, &SyncController::pairConfirmResult);
    QSignalSpy pendingSpy(&controller, &SyncController::notImplemented);

    controller.confirmPairing(QStringLiteral("req_pair1"), true);
    emit transport.pairConfirmResult(QJsonObject{
        {QStringLiteral("status"), QStringLiteral("not_implemented")}});

    QCOMPARE(pairingSpy.count(), 0);
    QCOMPARE(pendingSpy.count(), 1);
    QCOMPARE(pendingSpy.takeFirst().at(0).toString(),
             QStringLiteral("pair_confirm"));
}

void TestSyncController::settingsNotImplementedIsReported()
{
    FakeTransport transport;
    SyncController controller(&transport);
    QSignalSpy settingsSpy(&controller, &SyncController::settingsResult);
    QSignalSpy pendingSpy(&controller, &SyncController::notImplemented);

    controller.updateSettings(false, true);
    emit transport.settingsResult(QJsonObject{
        {QStringLiteral("status"), QStringLiteral("not_implemented")}});

    QCOMPARE(settingsSpy.count(), 0);
    QCOMPARE(pendingSpy.count(), 1);
    QCOMPARE(pendingSpy.takeFirst().at(0).toString(),
             QStringLiteral("settings"));
}

void TestSyncController::concurrentErrorClearsAllPendings()
{
    FakeTransport transport;
    SyncController controller(&transport);
    QSignalSpy settingsSpy(&controller, &SyncController::settingsResult);
    QSignalSpy failedSpy(&controller, &SyncController::failed);

    // 并发在途：设置更新与设备发现同时进行。全量清理语义（clearAllPending）
    // 下，任一流程的错误清空全部在途标记，其它流程随后到达的成功响应会被
    // stale 检查丢弃——SN-6 UI 必须序列化 discover/settings 交互，避免
    // 跨流程并发竞态（错误后不残留 pending，可立即重发）。
    controller.updateSettings(false, true);
    controller.discover();
    QCOMPARE(transport.settingsCalls.size(), 1);
    QCOMPARE(transport.discoverCalls, 1);

    emit transport.errorOccurred(QStringLiteral("HTTP_500"),
                                 QStringLiteral("discover failed"), QString());
    QCOMPARE(failedSpy.count(), 1);
    QCOMPARE(failedSpy.takeFirst().at(0).toString(),
             QStringLiteral("HTTP_500"));

    // 全量清理后，在途 settings 成功响应视为过期，不再上抛。
    emit transport.settingsResult(QJsonObject{
        {QStringLiteral("enabled"), false},
        {QStringLiteral("paused"), true}});
    QCOMPARE(settingsSpy.count(), 0);

    // 清理后控制器可立即重新发起请求。
    controller.updateSettings(true, false);
    QCOMPARE(transport.settingsCalls.size(), 2);
}

QTEST_MAIN(TestSyncController)
#include "t_sync_controller.moc"
