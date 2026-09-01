#include <QComboBox>
#include <QCoreApplication>
#include <QKeySequenceEdit>
#include <QLabel>
#include <QPushButton>
#include <QSignalSpy>
#include <QTest>
#include <QTextBrowser>

#include "widgets/CheckUpdateDialog.h"
#include "widgets/InfoDialog.h"
#include "widgets/SettingsDialog.h"

// SettingsDialog 语义测试：语言选择、OK/取消/Esc/关闭、稳定语言代码，
// 以及关于与法律四入口（检查更新/关于/条款/隐私）按钮与信号。
class TestSettingsDialog : public QObject
{
    Q_OBJECT

private slots:
    void initTestCase();
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
    void dialogIsNonModalSoClosingNeverBlocksChat();
    void buttonsHaveAccessibleNames();
    void dialogCanGrowForLongHints();
    void fourEntryButtonsExistAndNamed();
    void checkUpdateButtonEmitsSignal();
    void aboutUsButtonEmitsSignal();
    void termsButtonEmitsSignal();
    void privacyButtonEmitsSignal();
    void infoDialogRendersTitleAndBodyReadOnly();
    void infoDialogCloseOnlyClosesItself();
    void checkUpdateDialogShowsCurrentVersionAndGuide();
};

void TestSettingsDialog::initTestCase()
{
    // 与 main.cpp 相同的应用版本（PIXIU_VERSION 由 CMake 注入，单一事实源）：
    // 更新对话框展示当前版本，断言须与真实发布一致。
    QCoreApplication::setApplicationVersion(QStringLiteral(PIXIU_VERSION));
}

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

void TestSettingsDialog::dialogIsNonModalSoClosingNeverBlocksChat()
{
    // 回归：设置弹窗曾为模态；在 kylin-wlcom 上通过窗口“×”关闭模态弹窗后
    // 应用会残留模态状态，聊天框无法再响应点击。设置与其他功能弹窗一致
    // 保持非模态，保证“关弹窗只关弹窗、不关对话”。
    SettingsDialog dialog;
    QCOMPARE(dialog.windowModality(), Qt::NonModal);
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

void TestSettingsDialog::fourEntryButtonsExistAndNamed()
{
    // V-2：关于与法律四入口按钮齐全、可访问名非空、手型光标。
    SettingsDialog dialog;
    const char *const names[] = {
        "checkUpdateButton", "aboutUsButton", "termsButton", "privacyButton"};
    for (const char *name : names) {
        QPushButton *button =
            dialog.findChild<QPushButton *>(QLatin1String(name));
        QVERIFY2(button != nullptr, name);
        QVERIFY(!button->accessibleName().isEmpty());
        QCOMPARE(button->cursor().shape(), Qt::PointingHandCursor);
    }
}

void TestSettingsDialog::checkUpdateButtonEmitsSignal()
{
    SettingsDialog dialog;
    QSignalSpy spy(&dialog, &SettingsDialog::checkUpdateRequested);
    dialog.show();
    QPushButton *button = dialog.findChild<QPushButton *>(
        QStringLiteral("checkUpdateButton"));
    QVERIFY(button != nullptr);
    QTest::mouseClick(button, Qt::LeftButton);
    QCOMPARE(spy.count(), 1);
}

void TestSettingsDialog::aboutUsButtonEmitsSignal()
{
    SettingsDialog dialog;
    QSignalSpy spy(&dialog, &SettingsDialog::aboutUsRequested);
    dialog.show();
    QPushButton *button = dialog.findChild<QPushButton *>(
        QStringLiteral("aboutUsButton"));
    QVERIFY(button != nullptr);
    QTest::mouseClick(button, Qt::LeftButton);
    QCOMPARE(spy.count(), 1);
}

void TestSettingsDialog::termsButtonEmitsSignal()
{
    SettingsDialog dialog;
    QSignalSpy spy(&dialog, &SettingsDialog::termsRequested);
    dialog.show();
    QPushButton *button = dialog.findChild<QPushButton *>(
        QStringLiteral("termsButton"));
    QVERIFY(button != nullptr);
    QTest::mouseClick(button, Qt::LeftButton);
    QCOMPARE(spy.count(), 1);
}

void TestSettingsDialog::privacyButtonEmitsSignal()
{
    SettingsDialog dialog;
    QSignalSpy spy(&dialog, &SettingsDialog::privacyRequested);
    dialog.show();
    QPushButton *button = dialog.findChild<QPushButton *>(
        QStringLiteral("privacyButton"));
    QVERIFY(button != nullptr);
    QTest::mouseClick(button, Qt::LeftButton);
    QCOMPARE(spy.count(), 1);
}

void TestSettingsDialog::infoDialogRendersTitleAndBodyReadOnly()
{
    // InfoDialog：标题 + 只读正文渲染（关键词可断言）+ 非模态（不阻塞聊天）。
    InfoDialog dialog(tr("服务条款"),
                      QStringLiteral("PIXIU 为参赛作品，按现状提供。\n\n"
                                     "本软件不收集、不上传您的个人数据。"));
    QCOMPARE(dialog.windowTitle(), QStringLiteral("服务条款"));
    QTextBrowser *browser = dialog.findChild<QTextBrowser *>(
        QStringLiteral("infoTextBrowser"));
    QVERIFY(browser != nullptr);
    QVERIFY(browser->isReadOnly());
    const QString text = browser->toPlainText();
    QVERIFY(text.contains(QStringLiteral("参赛作品")));
    QVERIFY(text.contains(QStringLiteral("不上传")));
    QCOMPARE(dialog.windowModality(), Qt::NonModal);
}

void TestSettingsDialog::infoDialogCloseOnlyClosesItself()
{
    // 关闭按钮只隐藏本弹窗：非模态下不波及其他窗口。
    InfoDialog dialog(tr("关于 PIXIU"), QStringLiteral("正文"));
    QPushButton *close = dialog.findChild<QPushButton *>(
        QStringLiteral("infoCloseButton"));
    QVERIFY(close != nullptr);
    dialog.show();
    QTest::mouseClick(close, Qt::LeftButton);
    QVERIFY(!dialog.isVisible());
}

void TestSettingsDialog::checkUpdateDialogShowsCurrentVersionAndGuide()
{
    // 更新对话框：展示当前版本（与 applicationVersion 一致）；未注入升级
    // 控制器时禁用「一键升级」；「知道了」关闭。
    CheckUpdateDialog dialog;
    QLabel *current = dialog.findChild<QLabel *>(
        QStringLiteral("currentVersionLabel"));
    QVERIFY(current != nullptr);
    QVERIFY(current->text().contains(QCoreApplication::applicationVersion()));
    QPushButton *upgrade = dialog.findChild<QPushButton *>(
        QStringLiteral("upgradeButton"));
    QVERIFY(upgrade != nullptr);
    QVERIFY(!upgrade->isEnabled());   // 无控制器注入 → 禁用升级
    QCOMPARE(dialog.controller(), nullptr);
    QCOMPARE(dialog.windowModality(), Qt::NonModal);
    QPushButton *close = dialog.findChild<QPushButton *>(
        QStringLiteral("closeButton"));
    QVERIFY(close != nullptr);
    dialog.show();
    QTest::mouseClick(close, Qt::LeftButton);
    QVERIFY(!dialog.isVisible());
}

QTEST_MAIN(TestSettingsDialog)
#include "t_settings_dialog.moc"
