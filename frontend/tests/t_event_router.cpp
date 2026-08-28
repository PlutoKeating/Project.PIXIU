#include <QJsonArray>
#include <QJsonObject>
#include <QSignalSpy>
#include <QTest>

#include "app/EventRouter.h"

// EventRouter：WS 业务事件帧 → 语义信号的路由契约测试。
class TestEventRouter : public QObject
{
    Q_OBJECT

private slots:
    void memoryReadyIsForwarded();
    void conflictDetectedIsForwarded();
    void forgetConfirmationIsForwarded();
    void syncEventIsForwarded();
    void captureEventIsForwarded();
    void unknownEventIsIgnored();
    void nonObjectDataIsIgnored();
    void emptyEventIsIgnored();
    void captureEventWithoutDataIsIgnored();
};

void TestEventRouter::memoryReadyIsForwarded()
{
    EventRouter router;
    QSignalSpy spy(&router, &EventRouter::memoryReady);

    router.handleEvent(QJsonObject{
        {QStringLiteral("event"), QStringLiteral("memory_ready")},
        {QStringLiteral("data"), QJsonObject{
            {QStringLiteral("evidence_id"), QStringLiteral("evd_1")},
            {QStringLiteral("knowledge_id"), QStringLiteral("knw_1")},
            {QStringLiteral("title"), QStringLiteral("测试记忆")},
            {QStringLiteral("scope"), QStringLiteral("user:alice")}}}});

    QCOMPARE(spy.count(), 1);
    const QJsonObject data = spy.takeFirst().at(0).toJsonObject();
    QCOMPARE(data.value(QStringLiteral("knowledge_id")).toString(),
             QStringLiteral("knw_1"));
}

void TestEventRouter::conflictDetectedIsForwarded()
{
    EventRouter router;
    QSignalSpy spy(&router, &EventRouter::conflictDetected);

    router.handleEvent(QJsonObject{
        {QStringLiteral("event"), QStringLiteral("conflict_detected")},
        {QStringLiteral("data"), QJsonObject{
            {QStringLiteral("conflict_id"), QStringLiteral("cfl_1")},
            {QStringLiteral("knowledge_title"), QStringLiteral("2026年4月家庭支出清单")},
            {QStringLiteral("field"), QStringLiteral("body.items[2].amount")},
            {QStringLiteral("old_value"), 156},
            {QStringLiteral("new_value"), 186}}}});

    QCOMPARE(spy.count(), 1);
    const QList<QVariant> args = spy.takeFirst();
    QCOMPARE(args.at(0).toString(),
             QStringLiteral("2026年4月家庭支出清单"));
    QCOMPARE(args.at(1).toString(),
             QStringLiteral("body.items[2].amount"));
    QCOMPARE(args.at(2).toString(), QStringLiteral("156"));
    QCOMPARE(args.at(3).toString(), QStringLiteral("186"));
}

void TestEventRouter::forgetConfirmationIsForwarded()
{
    EventRouter router;
    QSignalSpy spy(&router, &EventRouter::forgetConfirmationReady);

    router.handleEvent(QJsonObject{
        {QStringLiteral("event"), QStringLiteral("forget_confirmation")},
        {QStringLiteral("data"), QJsonObject{
            {QStringLiteral("command"), QStringLiteral("忘记那张4月支出清单")},
            {QStringLiteral("targets"), QJsonArray{
                QJsonObject{
                    {QStringLiteral("type"), QStringLiteral("knowledge")},
                    {QStringLiteral("id"), QStringLiteral("knw_1")}}}},
            {QStringLiteral("expires_at"), 1714608100}}}});

    QCOMPARE(spy.count(), 1);
    const QList<QVariant> args = spy.takeFirst();
    QCOMPARE(args.at(0).toString(),
             QStringLiteral("忘记那张4月支出清单"));
    QCOMPARE(args.at(1).toJsonArray().size(), 1);
    QCOMPARE(args.at(3).toLongLong(), qint64(1714608100));
}

void TestEventRouter::syncEventIsForwarded()
{
    EventRouter router;
    QSignalSpy spy(&router, &EventRouter::syncEvent);

    router.handleEvent(QJsonObject{
        {QStringLiteral("event"), QStringLiteral("sync_event")},
        {QStringLiteral("data"), QJsonObject{
            {QStringLiteral("type"), QStringLiteral("PEER_ONLINE")},
            {QStringLiteral("peer_id"), QStringLiteral("dev_def")},
            {QStringLiteral("peer_name"), QStringLiteral("客厅一体机")},
            {QStringLiteral("timestamp"), 1714608000}}}});

    QCOMPARE(spy.count(), 1);
    const QJsonObject data = spy.takeFirst().at(0).toJsonObject();
    QCOMPARE(data.value(QStringLiteral("type")).toString(),
             QStringLiteral("PEER_ONLINE"));
}

void TestEventRouter::captureEventIsForwarded()
{
    EventRouter router;
    QSignalSpy spy(&router, &EventRouter::captureEvent);

    router.handleEvent(QJsonObject{
        {QStringLiteral("event"), QStringLiteral("capture_event")},
        {QStringLiteral("data"), QJsonObject{
            {QStringLiteral("source"), QStringLiteral("directory")},
            {QStringLiteral("status"), QStringLiteral("ingested")},
            {QStringLiteral("summary"), QStringLiteral("记住文件 支出清单.xlsx")},
            {QStringLiteral("ts"), 1756080000}}}});

    QCOMPARE(spy.count(), 1);
    const QList<QVariant> args = spy.takeFirst();
    QCOMPARE(args.at(0).toString(), QStringLiteral("directory"));
    QCOMPARE(args.at(1).toString(), QStringLiteral("ingested"));
    QCOMPARE(args.at(2).toString(), QStringLiteral("记住文件 支出清单.xlsx"));
    QCOMPARE(args.at(3).toLongLong(), qint64(1756080000));
}

void TestEventRouter::unknownEventIsIgnored()
{
    EventRouter router;
    QSignalSpy memorySpy(&router, &EventRouter::memoryReady);
    QSignalSpy conflictSpy(&router, &EventRouter::conflictDetected);
    QSignalSpy forgetSpy(&router, &EventRouter::forgetConfirmationReady);
    QSignalSpy syncSpy(&router, &EventRouter::syncEvent);
    QSignalSpy captureSpy(&router, &EventRouter::captureEvent);

    router.handleEvent(QJsonObject{
        {QStringLiteral("event"), QStringLiteral("some_future_event")},
        {QStringLiteral("data"), QJsonObject{{QStringLiteral("x"), 1}}}});
    QCOMPARE(memorySpy.count(), 0);
    QCOMPARE(conflictSpy.count(), 0);
    QCOMPARE(forgetSpy.count(), 0);
    QCOMPARE(syncSpy.count(), 0);
    QCOMPARE(captureSpy.count(), 0);
}

void TestEventRouter::nonObjectDataIsIgnored()
{
    EventRouter router;
    QSignalSpy memorySpy(&router, &EventRouter::memoryReady);

    router.handleEvent(QJsonObject{
        {QStringLiteral("event"), QStringLiteral("memory_ready")},
        {QStringLiteral("data"), QJsonArray{QStringLiteral("not-an-object")}}});
    QCOMPARE(memorySpy.count(), 0);
}

void TestEventRouter::emptyEventIsIgnored()
{
    EventRouter router;
    QSignalSpy memorySpy(&router, &EventRouter::memoryReady);

    router.handleEvent(QJsonObject());
    QCOMPARE(memorySpy.count(), 0);
}

void TestEventRouter::captureEventWithoutDataIsIgnored()
{
    EventRouter router;
    QSignalSpy captureSpy(&router, &EventRouter::captureEvent);

    // data 缺失：整帧合法（event 字段在），仅缺 data 键。
    router.handleEvent(QJsonObject{
        {QStringLiteral("event"), QStringLiteral("capture_event")}});
    QCOMPARE(captureSpy.count(), 0);

    // data 非对象：同样安全忽略，不发射 captureEvent。
    router.handleEvent(QJsonObject{
        {QStringLiteral("event"), QStringLiteral("capture_event")},
        {QStringLiteral("data"), QJsonArray{QStringLiteral("not-an-object")}}});
    QCOMPARE(captureSpy.count(), 0);
}

QTEST_MAIN(TestEventRouter)
#include "t_event_router.moc"
