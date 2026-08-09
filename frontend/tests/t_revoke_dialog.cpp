#include <QLabel>
#include <QPushButton>
#include <QSignalSpy>
#include <QTest>

#include "widgets/RevokeDialog.h"

// RevokeDialog：设备解绑二次确认语义测试。
class TestRevokeDialog : public QObject
{
    Q_OBJECT

private slots:
    void showsPeerName();
    void confirmEmitsAndHides();
    void cancelEmitsAndHides();
    void escEmitsCancelled();
    void cancelIsDefault();
};

void TestRevokeDialog::showsPeerName()
{
    RevokeDialog dialog;
    dialog.setPeerName(QStringLiteral("客厅一体机"));
    QLabel *nameLabel =
        dialog.findChild<QLabel *>(QStringLiteral("revokeNameLabel"));
    QVERIFY(nameLabel != nullptr);
    QVERIFY(nameLabel->text().contains(QStringLiteral("客厅一体机")));
}

void TestRevokeDialog::confirmEmitsAndHides()
{
    RevokeDialog dialog;
    QSignalSpy confirmedSpy(&dialog, &RevokeDialog::confirmed);
    dialog.show();

    QPushButton *confirmButton =
        dialog.findChild<QPushButton *>(QStringLiteral("revokeConfirmButton"));
    QVERIFY(confirmButton != nullptr);
    QTest::mouseClick(confirmButton, Qt::LeftButton);

    QCOMPARE(confirmedSpy.count(), 1);
    QVERIFY(!dialog.isVisible());
}

void TestRevokeDialog::cancelEmitsAndHides()
{
    RevokeDialog dialog;
    QSignalSpy cancelledSpy(&dialog, &RevokeDialog::cancelled);
    dialog.show();

    QPushButton *cancelButton =
        dialog.findChild<QPushButton *>(QStringLiteral("revokeCancelButton"));
    QVERIFY(cancelButton != nullptr);
    QTest::mouseClick(cancelButton, Qt::LeftButton);

    QCOMPARE(cancelledSpy.count(), 1);
    QVERIFY(!dialog.isVisible());
}

void TestRevokeDialog::escEmitsCancelled()
{
    RevokeDialog dialog;
    QSignalSpy cancelledSpy(&dialog, &RevokeDialog::cancelled);
    dialog.show();
    dialog.activateWindow();

    QTest::keyClick(&dialog, Qt::Key_Escape);
    QCOMPARE(cancelledSpy.count(), 1);
}

void TestRevokeDialog::cancelIsDefault()
{
    RevokeDialog dialog;
    QPushButton *cancelButton =
        dialog.findChild<QPushButton *>(QStringLiteral("revokeCancelButton"));
    QVERIFY(cancelButton != nullptr);
    QVERIFY(cancelButton->isDefault());
}

QTEST_MAIN(TestRevokeDialog)
#include "t_revoke_dialog.moc"
