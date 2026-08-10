#include <QJsonArray>
#include <QJsonObject>
#include <QSignalSpy>
#include <QTest>

#include "app/ForgetController.h"
#include "services/BackendTransport.h"

// 测试替身：记录 forget 调用并可由测试主动发射结果信号。
class FakeTransport : public BackendTransport
{
public:
    void connectToBackend() override {}
    void disconnectFromBackend() override {}
    quint64 queryMemory(const QString &, const QJsonObject &) override { return 0; }
    void writeMemory(const QJsonObject &) override {}
    void forget(const QString &command, bool confirm) override
    {
        lastCommand = command;
        lastConfirm = confirm;
        ++forgetCalls;
    }
    void listConflicts() override {}
    void preferenceHistory(const QString &) override {}
    void promoteMemory(const QJsonObject &) override {}
    void pairDevice(const QJsonObject &) override {}
    void listPeers() override {}
    void syncStatus() override {}
    void revokePeer(const QString &) override {}
    ConnectionState connectionState() const override { return ConnectionState::Connected; }
    QString baseUrl() const override { return QStringLiteral("http://127.0.0.1:8765"); }

    QString lastCommand;
    bool lastConfirm = false;
    int forgetCalls = 0;
};

// ForgetController 两段式确认契约测试。
class TestForgetController : public QObject
{
    Q_OBJECT

private slots:
    void isForgetIntentRecognizesCommands();
    void requestConfirmationSendsFirstPhase();
    void confirmSendsSecondPhase();
    void cancelClearsPendingCommand();
    void confirmRemoteSendsSecondPhaseOnly();
};

void TestForgetController::isForgetIntentRecognizesCommands()
{
    QVERIFY(ForgetController::isForgetIntent(QStringLiteral("忘记那张4月支出清单")));
    QVERIFY(ForgetController::isForgetIntent(QStringLiteral("遗忘旧工作流")));
    QVERIFY(ForgetController::isForgetIntent(QStringLiteral("  忘了这件事")));
    QVERIFY(!ForgetController::isForgetIntent(QStringLiteral("查一下支出")));
    QVERIFY(!ForgetController::isForgetIntent(QString()));
}

void TestForgetController::requestConfirmationSendsFirstPhase()
{
    FakeTransport transport;
    ForgetController controller(&transport);
    QSignalSpy readySpy(&controller, &ForgetController::confirmationReady);

    controller.requestConfirmation(QStringLiteral("忘记那张4月支出清单"));
    QCOMPARE(transport.forgetCalls, 1);
    QCOMPARE(transport.lastCommand, QStringLiteral("忘记那张4月支出清单"));
    QVERIFY(!transport.lastConfirm);

    QJsonObject response;
    response.insert(QStringLiteral("targets"), QJsonArray{
        QJsonObject{
            {QStringLiteral("type"), QStringLiteral("knowledge")},
            {QStringLiteral("id"), QStringLiteral("knw_1")},
            {QStringLiteral("title"), QStringLiteral("2026年4月家庭支出清单")}}});
    response.insert(QStringLiteral("cascade"),
                    QJsonObject{{QStringLiteral("evidence_count"), 1},
                                {QStringLiteral("relation_count"), 3}});
    response.insert(QStringLiteral("irreversible"), true);
    emit transport.forgetResult(response);

    QCOMPARE(readySpy.count(), 1);
    QCOMPARE(readySpy.takeFirst().at(0).toString(),
             QStringLiteral("忘记那张4月支出清单"));
}

void TestForgetController::confirmSendsSecondPhase()
{
    FakeTransport transport;
    ForgetController controller(&transport);

    controller.requestConfirmation(QStringLiteral("忘记那张4月支出清单"));
    QJsonObject confirmation;
    confirmation.insert(QStringLiteral("targets"), QJsonArray());
    emit transport.forgetResult(confirmation);

    QSignalSpy forgottenSpy(&controller, &ForgetController::forgotten);
    controller.confirm();
    QCOMPARE(transport.forgetCalls, 2);
    QVERIFY(transport.lastConfirm);

    QJsonObject result;
    result.insert(QStringLiteral("status"), QStringLiteral("forgotten"));
    result.insert(QStringLiteral("forgotten_ids"),
                  QJsonArray{QStringLiteral("knw_1"), QStringLiteral("evd_1")});
    emit transport.forgetResult(result);
    QCOMPARE(forgottenSpy.count(), 1);
}

void TestForgetController::cancelClearsPendingCommand()
{
    FakeTransport transport;
    ForgetController controller(&transport);

    controller.requestConfirmation(QStringLiteral("忘记那张4月支出清单"));
    controller.cancel();
    controller.confirm(); // 取消后不应发送第二阶段请求
    QCOMPARE(transport.forgetCalls, 1);
}

void TestForgetController::confirmRemoteSendsSecondPhaseOnly()
{
    FakeTransport transport;
    ForgetController controller(&transport);
    QSignalSpy forgottenSpy(&controller, &ForgetController::forgotten);

    // 远端确认：不经过 confirm=false 第一阶段，直接以 confirm=true 执行。
    controller.confirmRemote(QStringLiteral("忘记那张4月支出清单"));
    QCOMPARE(transport.forgetCalls, 1);
    QVERIFY(transport.lastConfirm);
    QCOMPARE(transport.lastCommand, QStringLiteral("忘记那张4月支出清单"));

    QJsonObject result;
    result.insert(QStringLiteral("status"), QStringLiteral("forgotten"));
    result.insert(QStringLiteral("forgotten_ids"),
                  QJsonArray{QStringLiteral("knw_1"), QStringLiteral("evd_1")});
    emit transport.forgetResult(result);
    QCOMPARE(forgottenSpy.count(), 1);

    // 空指令不发请求。
    controller.confirmRemote(QString());
    QCOMPARE(transport.forgetCalls, 1);
}

QTEST_MAIN(TestForgetController)
#include "t_forget_controller.moc"
