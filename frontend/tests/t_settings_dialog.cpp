#include <QComboBox>
#include <QPushButton>
#include <QSignalSpy>
#include <QTest>

#include "widgets/SettingsDialog.h"

// SettingsDialog 语义测试：语言选择、OK/取消/Esc/关闭与稳定语言代码。
class TestSettingsDialog : public QObject
{
    Q_OBJECT

private slots:
    void defaultLanguageFollowsSystem();
    void setLanguageSelectsSavedValue();
    void languageOptionsCarryStableCodes();
    void okAcceptsWithSelectedLanguage();
    void escapeCancels();
    void closeCancels();
    void buttonsHaveAccessibleNames();
};

void TestSettingsDialog::defaultLanguageFollowsSystem()
{
    SettingsDialog dialog;
    QCOMPARE(dialog.selectedLanguage(), QStringLiteral("system"));
}

void TestSettingsDialog::setLanguageSelectsSavedValue()
{
    SettingsDialog dialog;
    dialog.setLanguage(QStringLiteral("en_US"));
    QCOMPARE(dialog.selectedLanguage(), QStringLiteral("en_US"));
    dialog.setLanguage(QStringLiteral("zh_CN"));
    QCOMPARE(dialog.selectedLanguage(), QStringLiteral("zh_CN"));
    // 未知/空值回退“跟随系统”，保证旧配置兼容。
    dialog.setLanguage(QStringLiteral("unknown"));
    QCOMPARE(dialog.selectedLanguage(), QStringLiteral("system"));
}

void TestSettingsDialog::languageOptionsCarryStableCodes()
{
    SettingsDialog dialog;
    QComboBox *combo =
        dialog.findChild<QComboBox *>(QStringLiteral("languageCombo"));
    QVERIFY(combo != nullptr);
    QCOMPARE(combo->findData(QStringLiteral("system")), 0);
    QCOMPARE(combo->findData(QStringLiteral("zh_CN")), 1);
    QCOMPARE(combo->findData(QStringLiteral("en_US")), 2);
}

void TestSettingsDialog::okAcceptsWithSelectedLanguage()
{
    SettingsDialog dialog;
    QSignalSpy accepted(&dialog, &QDialog::accepted);
    QComboBox *combo =
        dialog.findChild<QComboBox *>(QStringLiteral("languageCombo"));
    QVERIFY(combo != nullptr);
    combo->setCurrentIndex(combo->findData(QStringLiteral("en_US")));

    dialog.show();
    QPushButton *ok =
        dialog.findChild<QPushButton *>(QStringLiteral("settingsOkButton"));
    QVERIFY(ok != nullptr);
    QTest::mouseClick(ok, Qt::LeftButton);

    QCOMPARE(accepted.count(), 1);
    QCOMPARE(dialog.selectedLanguage(), QStringLiteral("en_US"));
    QCOMPARE(dialog.result(), int(QDialog::Accepted));
}

void TestSettingsDialog::escapeCancels()
{
    SettingsDialog dialog;
    QSignalSpy cancelled(&dialog, &SettingsDialog::cancelled);
    dialog.show();
    QTest::keyClick(&dialog, Qt::Key_Escape);
    QCOMPARE(cancelled.count(), 1);
    QCOMPARE(dialog.result(), int(QDialog::Rejected));
    QVERIFY(!dialog.isVisible());
}

void TestSettingsDialog::closeCancels()
{
    SettingsDialog dialog;
    QSignalSpy cancelled(&dialog, &SettingsDialog::cancelled);
    dialog.show();
    dialog.close();
    QCOMPARE(cancelled.count(), 1);
    QCOMPARE(dialog.result(), int(QDialog::Rejected));
}

void TestSettingsDialog::buttonsHaveAccessibleNames()
{
    SettingsDialog dialog;
    QPushButton *ok =
        dialog.findChild<QPushButton *>(QStringLiteral("settingsOkButton"));
    QPushButton *cancel =
        dialog.findChild<QPushButton *>(QStringLiteral("settingsCancelButton"));
    QVERIFY(ok != nullptr);
    QVERIFY(cancel != nullptr);
    QVERIFY(!ok->accessibleName().isEmpty());
    QVERIFY(!cancel->accessibleName().isEmpty());
}

QTEST_MAIN(TestSettingsDialog)
#include "t_settings_dialog.moc"
