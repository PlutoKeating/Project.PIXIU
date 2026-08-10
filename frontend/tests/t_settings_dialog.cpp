#include <QComboBox>
#include <QKeySequenceEdit>
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
    void defaultShortcutIsDefaultSequence();
    void setShortcutRoundTrip();
    void okDisabledForEmptyOrPlainKeyShortcut();
    void okEnabledForModifiedShortcut();
    void okAcceptsWithSelectedLanguage();
    void escapeCancels();
    void closeCancels();
    void buttonsHaveAccessibleNames();
    void dialogCanGrowForLongHints();
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

void TestSettingsDialog::defaultShortcutIsDefaultSequence()
{
    SettingsDialog dialog;
    QCOMPARE(dialog.selectedShortcut(),
             QKeySequence(QStringLiteral("Ctrl+Alt+P")));
}

void TestSettingsDialog::setShortcutRoundTrip()
{
    SettingsDialog dialog;
    dialog.setShortcut(QKeySequence(QStringLiteral("Ctrl+Alt+K")));
    QCOMPARE(dialog.selectedShortcut(),
             QKeySequence(QStringLiteral("Ctrl+Alt+K")));
    // 空值回退默认序列，保证旧配置兼容。
    dialog.setShortcut(QKeySequence());
    QCOMPARE(dialog.selectedShortcut(),
             QKeySequence(QStringLiteral("Ctrl+Alt+P")));
}

void TestSettingsDialog::okDisabledForEmptyOrPlainKeyShortcut()
{
    SettingsDialog dialog;
    QKeySequenceEdit *edit =
        dialog.findChild<QKeySequenceEdit *>(QStringLiteral("shortcutEdit"));
    QPushButton *ok =
        dialog.findChild<QPushButton *>(QStringLiteral("settingsOkButton"));
    QVERIFY(edit != nullptr);
    QVERIFY(ok != nullptr);

    edit->setKeySequence(QKeySequence());
    QVERIFY(!ok->isEnabled());
    // 裸键（无修饰键）会劫持桌面输入，不允许保存。
    edit->setKeySequence(QKeySequence(QStringLiteral("P")));
    QVERIFY(!ok->isEnabled());
}

void TestSettingsDialog::okEnabledForModifiedShortcut()
{
    SettingsDialog dialog;
    QKeySequenceEdit *edit =
        dialog.findChild<QKeySequenceEdit *>(QStringLiteral("shortcutEdit"));
    QPushButton *ok =
        dialog.findChild<QPushButton *>(QStringLiteral("settingsOkButton"));
    QVERIFY(edit != nullptr);
    QVERIFY(ok != nullptr);
    QVERIFY(ok->isEnabled());

    edit->setKeySequence(QKeySequence(QStringLiteral("Ctrl+P")));
    QVERIFY(ok->isEnabled());
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
    QCOMPARE(ok->cursor().shape(), Qt::PointingHandCursor);
    QCOMPARE(cancel->cursor().shape(), Qt::PointingHandCursor);
}

void TestSettingsDialog::dialogCanGrowForLongHints()
{
    SettingsDialog dialog;
    // 固定尺寸会裁剪英文长提示；对话框保留最小尺寸且允许随内容增高。
    QVERIFY(dialog.minimumWidth() >= 400);
    QVERIFY(dialog.minimumHeight() >= 330);
    QVERIFY(dialog.maximumHeight() > 500);
}

QTEST_MAIN(TestSettingsDialog)
#include "t_settings_dialog.moc"
