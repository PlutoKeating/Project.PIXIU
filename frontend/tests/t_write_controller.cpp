#include <QJsonObject>
#include <QSignalSpy>
#include <QTest>

#include "app/WriteController.h"
#include "services/BackendTransport.h"

// 测试替身：记录 writeMemory 载荷并主动发射结果信号。
class FakeTransport : public BackendTransport
{
public:
    void connectToBackend() override {}
    void disconnectFromBackend() override {}
    quint64 queryMemory(const QString &, const QJsonObject &) override { return 0; }
    void writeMemory(const QJsonObject &payload) override { lastPayload = payload; }
    void forget(const QString &, bool) override {}
    void listConflicts() override {}
    void preferenceHistory(const QString &) override {}
    void promoteMemory(const QJsonObject &) override {}
    void pairDevice(const QJsonObject &) override {}
    void listPeers() override {}
    void syncStatus() override {}
    void revokePeer(const QString &) override {}
    ConnectionState connectionState() const override { return ConnectionState::Connected; }
    QString baseUrl() const override { return QStringLiteral("http://127.0.0.1:8765"); }

    QJsonObject lastPayload;
};

// WriteController 契约测试：/memory/write 载荷构造与结果上抛。
class TestWriteController : public QObject
{
    Q_OBJECT

private slots:
    void submitBuildsContractPayload();
    void submitWithImageAddsOcrContext();
    void writeAcknowledgedIsForwarded();
    void transportErrorBecomesWriteFailed();
};

void TestWriteController::submitBuildsContractPayload()
{
    FakeTransport transport;
    WriteController controller(&transport);

    controller.submit(QStringLiteral("标题"),
                      QStringLiteral("内容"),
                      QStringLiteral("shared:home"));

    const QJsonObject payload = transport.lastPayload;
    QCOMPARE(payload.value(QStringLiteral("source_type")).toString(),
             QStringLiteral("MANUAL_CONFIG"));
    QCOMPARE(payload.value(QStringLiteral("scope")).toString(),
             QStringLiteral("shared:home"));
    const QJsonObject raw = payload.value(QStringLiteral("raw")).toObject();
    QCOMPARE(raw.value(QStringLiteral("title")).toString(), QStringLiteral("标题"));
    QCOMPARE(raw.value(QStringLiteral("body")).toObject()
                 .value(QStringLiteral("text")).toString(),
             QStringLiteral("内容"));
    QVERIFY(!payload.contains(QStringLiteral("context")));
}

void TestWriteController::submitWithImageAddsOcrContext()
{
    FakeTransport transport;
    WriteController controller(&transport);

    controller.submit(QStringLiteral("标题"),
                      QStringLiteral("内容"),
                      QStringLiteral("user:alice"),
                      QStringLiteral("/tmp/scan.png"));

    const QJsonObject context =
        transport.lastPayload.value(QStringLiteral("context")).toObject();
    QCOMPARE(context.value(QStringLiteral("attachment_path")).toString(),
             QStringLiteral("/tmp/scan.png"));
    QCOMPARE(context.value(QStringLiteral("ocr_pending")).toBool(), true);
}

void TestWriteController::writeAcknowledgedIsForwarded()
{
    FakeTransport transport;
    WriteController controller(&transport);
    QSignalSpy acceptedSpy(&controller, &WriteController::writeAccepted);

    QJsonObject response{
        {QStringLiteral("evidence_id"), QStringLiteral("evd_01H")},
        {QStringLiteral("status"), QStringLiteral("accepted")},
        {QStringLiteral("preference_count"), 2}};
    emit transport.writeAcknowledged(response);

    QCOMPARE(acceptedSpy.count(), 1);
    QCOMPARE(acceptedSpy.takeFirst().at(0).toJsonObject()
                 .value(QStringLiteral("evidence_id")).toString(),
             QStringLiteral("evd_01H"));
}

void TestWriteController::transportErrorBecomesWriteFailed()
{
    FakeTransport transport;
    WriteController controller(&transport);
    QSignalSpy failedSpy(&controller, &WriteController::writeFailed);

    emit transport.errorOccurred(QStringLiteral("NETWORK_ERROR"),
                                 QStringLiteral("connection refused"), QString());

    QCOMPARE(failedSpy.count(), 1);
    const QList<QVariant> args = failedSpy.takeFirst();
    QCOMPARE(args.at(0).toString(), QStringLiteral("NETWORK_ERROR"));
    QCOMPARE(args.at(1).toString(), QStringLiteral("connection refused"));
}

QTEST_MAIN(TestWriteController)
#include "t_write_controller.moc"
