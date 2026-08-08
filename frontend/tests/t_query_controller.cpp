#include <QJsonObject>
#include <QSignalSpy>
#include <QTest>

#include "app/QueryController.h"
#include "services/BackendTransport.h"

// 测试替身：记录 queryMemory 调用并返回递增请求 ID。
class FakeTransport : public BackendTransport
{
public:
    void connectToBackend() override {}
    void disconnectFromBackend() override {}
    quint64 queryMemory(const QString &text, const QJsonObject &hint) override
    {
        lastText = text;
        lastHint = hint;
        return ++nextRequestId;
    }
    void writeMemory(const QJsonObject &) override {}
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

    quint64 nextRequestId = 0;
    QString lastText;
    QJsonObject lastHint;
};

// QueryController 状态机测试：加载/结果/空结果/失败/过期响应/取消。
class TestQueryController : public QObject
{
    Q_OBJECT

private slots:
    void submitEmitsUserAndThinking();
    void resultEmitsAnswerReady();
    void emptyAnswerEmitsEmptyResult();
    void errorEmitsQueryFailedWithOriginalText();
    void staleResultIsIgnored();
    void newSubmitCancelsPreviousResult();
};

void TestQueryController::submitEmitsUserAndThinking()
{
    FakeTransport transport;
    QueryController controller(&transport);
    QSignalSpy userSpy(&controller, &QueryController::userMessageReady);
    QSignalSpy thinkingSpy(&controller, &QueryController::thinkingChanged);

    controller.submit(QStringLiteral("水电燃气花了多少钱？"));

    QCOMPARE(userSpy.count(), 1);
    QCOMPARE(userSpy.takeFirst().at(0).toString(),
             QStringLiteral("水电燃气花了多少钱？"));
    QCOMPARE(thinkingSpy.count(), 1);
    QCOMPARE(thinkingSpy.takeFirst().at(0).toBool(), true);
    QCOMPARE(transport.lastText, QStringLiteral("水电燃气花了多少钱？"));
    QCOMPARE(transport.lastHint.value(QStringLiteral("top_k")).toInt(), 5);
}

void TestQueryController::resultEmitsAnswerReady()
{
    FakeTransport transport;
    QueryController controller(&transport);
    QSignalSpy answerSpy(&controller, &QueryController::answerReady);
    QSignalSpy thinkingSpy(&controller, &QueryController::thinkingChanged);

    controller.submit(QStringLiteral("问题"));
    const quint64 id = transport.nextRequestId;
    QJsonObject atom{
        {QStringLiteral("answer"), QStringLiteral("434.50 元")},
        {QStringLiteral("confidence"), 0.93},
        {QStringLiteral("latency_ms"), 210}};
    controller.handleQueryResult(id, atom);

    QCOMPARE(answerSpy.count(), 1);
    const MemoryAtom memory = answerSpy.takeFirst().at(0).value<MemoryAtom>();
    QCOMPARE(memory.answer, QStringLiteral("434.50 元"));
    QVERIFY(qAbs(memory.confidence - 0.93) < 1e-9);
    QCOMPARE(memory.latencyMs, 210);
    QCOMPARE(thinkingSpy.count(), 2);
    QCOMPARE(thinkingSpy.last().at(0).toBool(), false);
}

void TestQueryController::emptyAnswerEmitsEmptyResult()
{
    FakeTransport transport;
    QueryController controller(&transport);
    QSignalSpy emptySpy(&controller, &QueryController::emptyResultReady);
    QSignalSpy answerSpy(&controller, &QueryController::answerReady);

    controller.submit(QStringLiteral("问题"));
    controller.handleQueryResult(transport.nextRequestId, QJsonObject{});

    QCOMPARE(emptySpy.count(), 1);
    QCOMPARE(answerSpy.count(), 0);
}

void TestQueryController::errorEmitsQueryFailedWithOriginalText()
{
    FakeTransport transport;
    QueryController controller(&transport);
    QSignalSpy failedSpy(&controller, &QueryController::queryFailed);

    controller.submit(QStringLiteral("保留这段输入"));
    controller.handleQueryError(transport.nextRequestId,
                                QStringLiteral("NETWORK_ERROR"),
                                QStringLiteral("connection refused"));

    QCOMPARE(failedSpy.count(), 1);
    const QList<QVariant> args = failedSpy.takeFirst();
    QCOMPARE(args.at(0).toString(), QStringLiteral("保留这段输入"));
    QCOMPARE(args.at(1).toString(), QStringLiteral("NETWORK_ERROR"));
    QCOMPARE(args.at(2).toString(), QStringLiteral("connection refused"));
}

void TestQueryController::staleResultIsIgnored()
{
    FakeTransport transport;
    QueryController controller(&transport);
    QSignalSpy answerSpy(&controller, &QueryController::answerReady);
    QSignalSpy failedSpy(&controller, &QueryController::queryFailed);

    // 无在途查询时到达的响应视为过期。
    controller.handleQueryResult(1, QJsonObject{{QStringLiteral("answer"),
                                                 QStringLiteral("x")}});
    controller.handleQueryError(1, QStringLiteral("NETWORK_ERROR"), QString());
    QCOMPARE(answerSpy.count(), 0);
    QCOMPARE(failedSpy.count(), 0);

    // 提交后到达的错误请求 ID 同样忽略。
    controller.submit(QStringLiteral("问题"));
    controller.handleQueryResult(transport.nextRequestId + 100, QJsonObject{});
    controller.handleQueryError(transport.nextRequestId + 100,
                                QStringLiteral("TIMEOUT"), QString());
    QCOMPARE(answerSpy.count(), 0);
    QCOMPARE(failedSpy.count(), 0);
}

void TestQueryController::newSubmitCancelsPreviousResult()
{
    FakeTransport transport;
    QueryController controller(&transport);
    QSignalSpy answerSpy(&controller, &QueryController::answerReady);

    controller.submit(QStringLiteral("第一个问题"));
    const quint64 firstId = transport.nextRequestId;
    controller.submit(QStringLiteral("第二个问题"));

    // 旧请求的响应过期，不打断当前查询。
    controller.handleQueryResult(firstId,
                                 QJsonObject{{QStringLiteral("answer"),
                                              QStringLiteral("旧答案")}});
    QCOMPARE(answerSpy.count(), 0);

    controller.handleQueryResult(transport.nextRequestId,
                                 QJsonObject{{QStringLiteral("answer"),
                                              QStringLiteral("新答案")}});
    QCOMPARE(answerSpy.count(), 1);
    QCOMPARE(answerSpy.takeFirst().at(0).value<MemoryAtom>().answer,
             QStringLiteral("新答案"));
}

QTEST_MAIN(TestQueryController)
#include "t_query_controller.moc"
