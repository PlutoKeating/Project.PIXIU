#include <QJsonArray>
#include <QJsonObject>
#include <QApplication>
#include <QLabel>
#include <QPushButton>
#include <QSignalSpy>
#include <QTest>

#include "widgets/ForgetDialog.h"

// ForgetDialog 影响范围展示与确认/取消信号测试。
class TestForgetDialog : public QObject
{
    Q_OBJECT

private slots:
    void summaryShowsTargetsAndCascade();
    void confirmEmitsConfirmed();
    void cancelEmitsCancelled();
    void escEmitsCancelled();
    void cancelIsDefaultButton();
    void cancelReceivesInitialFocus();
    void buttonsShowPointerCursor();
};

QJsonObject sampleConfirmation()
{
    QJsonObject response;
    response.insert(QStringLiteral("targets"), QJsonArray{
        QJsonObject{
            {QStringLiteral("type"), QStringLiteral("knowledge")},
            {QStringLiteral("id"), QStringLiteral("knw_1")},
            {QStringLiteral("title"), QStringLiteral("2026年4月家庭支出清单")}}});
    response.insert(QStringLiteral("cascade"),
                    QJsonObject{{QStringLiteral("evidence_count"), 1},
                                {QStringLiteral("relation_count"), 3}});
    return response;
}

void TestForgetDialog::summaryShowsTargetsAndCascade()
{
    ForgetDialog dialog;
    const QJsonObject response = sampleConfirmation();
    dialog.setForgetTargets(response.value(QStringLiteral("targets")).toArray(),
                            response.value(QStringLiteral("cascade")).toObject());

    QLabel *label = dialog.findChild<QLabel *>();
    QVERIFY(label != nullptr);
    QVERIFY(label->text().contains(QStringLiteral("2026年4月家庭支出清单")));
    QVERIFY(label->text().contains(QStringLiteral("证据 1 条")));
    QVERIFY(label->text().contains(QStringLiteral("关系 3 条")));
    QVERIFY(label->text().contains(QStringLiteral("不可撤销")));
}

void TestForgetDialog::confirmEmitsConfirmed()
{
    ForgetDialog dialog;
    QSignalSpy spy(&dialog, &ForgetDialog::confirmed);

    QPushButton *confirm = nullptr;
    const QList<QPushButton *> buttons = dialog.findChildren<QPushButton *>();
    for (QPushButton *button : buttons) {
        if (button->text() == QStringLiteral("确认遗忘")) {
            confirm = button;
            break;
        }
    }
    QVERIFY(confirm != nullptr);
    QTest::mouseClick(confirm, Qt::LeftButton);
    QCOMPARE(spy.count(), 1);
}

void TestForgetDialog::cancelEmitsCancelled()
{
    ForgetDialog dialog;
    QSignalSpy spy(&dialog, &ForgetDialog::cancelled);

    const QList<QPushButton *> buttons = dialog.findChildren<QPushButton *>();
    QCOMPARE(buttons.size(), 2);
    QPushButton *cancel = buttons.at(0);
    QTest::mouseClick(cancel, Qt::LeftButton);
    QCOMPARE(spy.count(), 1);
}

void TestForgetDialog::escEmitsCancelled()
{
    ForgetDialog dialog;
    QSignalSpy spy(&dialog, &ForgetDialog::cancelled);

    dialog.show();
    QVERIFY(dialog.isVisible());
    QTest::keyClick(&dialog, Qt::Key_Escape);

    QCOMPARE(spy.count(), 1);
    QVERIFY(!dialog.isVisible());
}

void TestForgetDialog::cancelIsDefaultButton()
{
    ForgetDialog dialog;

    const QList<QPushButton *> buttons = dialog.findChildren<QPushButton *>();
    QPushButton *cancel = nullptr;
    QPushButton *confirm = nullptr;
    for (QPushButton *button : buttons) {
        if (button->text() == QStringLiteral("取消")) {
            cancel = button;
        } else if (button->text() == QStringLiteral("确认遗忘")) {
            confirm = button;
        }
    }
    QVERIFY(cancel != nullptr);
    QVERIFY(confirm != nullptr);
    QVERIFY(cancel->isDefault());
    QVERIFY(!confirm->isDefault());
}

void TestForgetDialog::cancelReceivesInitialFocus()
{
    ForgetDialog dialog;
    dialog.show();

    QPushButton *cancel =
        dialog.findChild<QPushButton *>(QStringLiteral("forgetCancelButton"));
    QVERIFY(cancel != nullptr);
    QTRY_COMPARE(QApplication::focusWidget(), cancel);
}

void TestForgetDialog::buttonsShowPointerCursor()
{
    ForgetDialog dialog;
    QPushButton *cancel =
        dialog.findChild<QPushButton *>(QStringLiteral("forgetCancelButton"));
    QPushButton *confirm =
        dialog.findChild<QPushButton *>(QStringLiteral("dangerConfirmButton"));
    QVERIFY(cancel != nullptr);
    QVERIFY(confirm != nullptr);
    QCOMPARE(cancel->cursor().shape(), Qt::PointingHandCursor);
    QCOMPARE(confirm->cursor().shape(), Qt::PointingHandCursor);
}

QTEST_MAIN(TestForgetDialog)
#include "t_forget_dialog.moc"
