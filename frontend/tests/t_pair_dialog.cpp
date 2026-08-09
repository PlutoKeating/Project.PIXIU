#include <QComboBox>
#include <QJsonObject>
#include <QLabel>
#include <QLineEdit>
#include <QPushButton>
#include <QSignalSpy>
#include <QStackedWidget>
#include <QTest>

#include "widgets/PairDialog.h"

// PairDialog 壳测试：PIN 门控、确认载荷、取消/Esc、二维码占位与反馈状态。
class TestPairDialog : public QObject
{
    Q_OBJECT

private slots:
    void confirmDisabledWithoutValidPin();
    void confirmEmitsPayloadAndHides();
    void cancelHidesWithoutEmit();
    void escHidesWithoutEmit();
    void qrModeDisablesConfirm();
    void feedbackShowsStatus();
    void accessibilityNamesPresent();
};

namespace {
QLineEdit *pinInput(PairDialog *dialog)
{
    return dialog->findChild<QLineEdit *>(QStringLiteral("pairPinInput"));
}

QPushButton *confirmButton(PairDialog *dialog)
{
    return dialog->findChild<QPushButton *>(QStringLiteral("pairConfirmButton"));
}

QPushButton *cancelButton(PairDialog *dialog)
{
    return dialog->findChild<QPushButton *>(QStringLiteral("pairCancelButton"));
}
}

void TestPairDialog::confirmDisabledWithoutValidPin()
{
    PairDialog dialog;
    QVERIFY(!confirmButton(&dialog)->isEnabled());
    pinInput(&dialog)->setText(QStringLiteral("123"));
    QVERIFY(!confirmButton(&dialog)->isEnabled());
    pinInput(&dialog)->setText(QStringLiteral("12345"));
    QVERIFY(!confirmButton(&dialog)->isEnabled());
}

void TestPairDialog::confirmEmitsPayloadAndHides()
{
    PairDialog dialog;
    dialog.show();
    QSignalSpy spy(&dialog, &PairDialog::pairRequested);

    pinInput(&dialog)->setText(QStringLiteral("123456"));
    QVERIFY(confirmButton(&dialog)->isEnabled());
    QTest::mouseClick(confirmButton(&dialog), Qt::LeftButton);

    QCOMPARE(spy.count(), 1);
    const QJsonObject payload = spy.takeFirst().at(0).toJsonObject();
    QCOMPARE(payload.value(QStringLiteral("method")).toString(),
             QStringLiteral("PIN"));
    QCOMPARE(payload.value(QStringLiteral("pin")).toString(),
             QStringLiteral("123456"));
    QCOMPARE(payload.value(QStringLiteral("token")).toString(), QString());
    QVERIFY(!dialog.isVisible());
}

void TestPairDialog::cancelHidesWithoutEmit()
{
    PairDialog dialog;
    dialog.show();
    QSignalSpy requestSpy(&dialog, &PairDialog::pairRequested);
    QSignalSpy cancelSpy(&dialog, &PairDialog::cancelled);

    QTest::mouseClick(cancelButton(&dialog), Qt::LeftButton);

    QCOMPARE(cancelSpy.count(), 1);
    QCOMPARE(requestSpy.count(), 0);
    QVERIFY(!dialog.isVisible());
}

void TestPairDialog::escHidesWithoutEmit()
{
    PairDialog dialog;
    dialog.show();
    QSignalSpy requestSpy(&dialog, &PairDialog::pairRequested);
    QSignalSpy cancelSpy(&dialog, &PairDialog::cancelled);

    QTest::keyClick(&dialog, Qt::Key_Escape);

    QCOMPARE(cancelSpy.count(), 1);
    QCOMPARE(requestSpy.count(), 0);
    QVERIFY(!dialog.isVisible());
}

void TestPairDialog::qrModeDisablesConfirm()
{
    PairDialog dialog;
    QComboBox *combo =
        dialog.findChild<QComboBox *>(QStringLiteral("pairMethodCombo"));
    QVERIFY(combo != nullptr);
    QStackedWidget *stack = dialog.findChild<QStackedWidget *>();
    QVERIFY(stack != nullptr);

    combo->setCurrentIndex(1);
    QCOMPARE(stack->currentIndex(), 1);
    QVERIFY(!confirmButton(&dialog)->isEnabled());

    combo->setCurrentIndex(0);
    pinInput(&dialog)->setText(QStringLiteral("123456"));
    QVERIFY(confirmButton(&dialog)->isEnabled());
}

void TestPairDialog::feedbackShowsStatus()
{
    PairDialog dialog;
    QLabel *status =
        dialog.findChild<QLabel *>(QStringLiteral("pairStatusLabel"));
    QVERIFY(status != nullptr);
    QVERIFY(status->isHidden());

    dialog.setResultFeedback(true, QStringLiteral("配对成功：客厅一体机"));
    QVERIFY(!status->isHidden());
    QCOMPARE(status->text(), QStringLiteral("配对成功：客厅一体机"));
}

void TestPairDialog::accessibilityNamesPresent()
{
    PairDialog dialog;
    QVERIFY(!pinInput(&dialog)->accessibleName().isEmpty());
    QVERIFY(!confirmButton(&dialog)->accessibleName().isEmpty());
    QVERIFY(!cancelButton(&dialog)->accessibleName().isEmpty());
}

QTEST_MAIN(TestPairDialog)
#include "t_pair_dialog.moc"
