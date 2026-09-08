#include "HostTray.h"
#include "HostWindowPin.h"
#include "SettingsWorkspace.h"
#include "HostCloseGuard.h"
#include "app/ShortcutManager.h"
#include <QAction>
#include <QCheckBox>
#include <QKeySequenceEdit>
#include <QLabel>
#include <QPushButton>
#include <QSettings>
#include <QSignalSpy>
#include <QTemporaryDir>
#include <QTemporaryFile>
#include <QMessageBox>
#include <QTimer>
#include <QTest>

class HostShortcutTest : public QObject
{
    Q_OBJECT
    QTemporaryDir config;
private slots:
    void initTestCase()
    {
        QVERIFY(config.isValid());
        QCoreApplication::setOrganizationName("pixiu-shortcut-test");
        QCoreApplication::setApplicationName("host");
        QSettings::setDefaultFormat(QSettings::IniFormat);
    }
    void init()
    {
        QSettings::setPath(QSettings::IniFormat, QSettings::UserScope, config.path());
        QSettings settings;
        settings.clear();
        settings.sync();
    }
    void settingsApplyPersistAndReplaceOneBinding()
    {
        QWidget host;
        pixiu::HostTray tray(&host);
        pixiu::SettingsWorkspace settings(&host);
        auto *editor = settings.findChild<QKeySequenceEdit *>("activationShortcut");
        auto *apply = settings.findChild<QPushButton *>("applyActivationShortcut");
        auto *status = settings.findChild<QLabel *>("activationShortcutStatus");
        QVERIFY(editor); QVERIFY(apply); QVERIFY(status);
        auto *manager = host.findChild<ShortcutManager *>();
        QVERIFY(manager);
        QCOMPARE(editor->keySequence(), QKeySequence("Ctrl+Alt+P"));
        editor->setKeySequence(QKeySequence("Ctrl+Alt+K"));
        QCOMPARE(manager->currentSequence(), QKeySequence("Ctrl+Alt+P"));
        apply->click();
        QCOMPARE(manager->currentSequence(), QKeySequence("Ctrl+Alt+K"));
        QCOMPARE(host.findChildren<ShortcutManager *>().size(), 1);
        QVERIFY(status->text().contains("Ctrl+Alt+K"));
        QVERIFY(status->text().contains(QStringLiteral("仅应用内")));
        QVERIFY(!settings.hasUnsavedChanges());
        QVERIFY(host.findChild<QAction *>("hostTrayShow")->text().contains("Ctrl+Alt+K"));
        host.show(); host.activateWindow();
        QVERIFY(QTest::qWaitForWindowActive(&host));
        host.setFocus();
        QSignalSpy activated(manager, &ShortcutManager::toggleRequested);
        QTest::keyClick(&host, Qt::Key_P, Qt::ControlModifier | Qt::AltModifier);
        QCOMPARE(activated.count(), 0);
        QTest::keyClick(&host, Qt::Key_K, Qt::ControlModifier | Qt::AltModifier);
        QCOMPARE(activated.count(), 1);
        host.close();
        QWidget restarted;
        pixiu::HostTray restored(&restarted);
        QCOMPARE(restarted.findChild<ShortcutManager *>()->currentSequence(), QKeySequence("Ctrl+Alt+K"));
    }
    void settingsPinUsesTheSameHostWithoutSavingConfiguration()
    {
        QWidget host;
        pixiu::HostTray tray(&host);
        pixiu::SettingsWorkspace settings(&host);
        auto *pin = settings.findChild<QCheckBox *>("hostWindowPin");
        auto *status = settings.findChild<QLabel *>("hostWindowPinStatus");
        QVERIFY(pin); QVERIFY(status);
        QCOMPARE(host.findChildren<pixiu::HostWindowPin *>().size(), 1);
        const auto keys = QSettings().allKeys();
        pin->click();
        QVERIFY(host.windowFlags().testFlag(Qt::WindowStaysOnTopHint));
        QVERIFY(pin->isChecked());
        QVERIFY(status->text().contains(QStringLiteral("Qt 兼容路径")));
        pin->click();
        QVERIFY(!host.windowFlags().testFlag(Qt::WindowStaysOnTopHint));
        QCOMPARE(QSettings().allKeys(), keys);
        QVERIFY(!settings.hasUnsavedChanges());
    }
    void invalidInputKeepsBindingAndSavedValue()
    {
        QWidget host;
        pixiu::HostTray tray(&host);
        pixiu::SettingsWorkspace settings(&host);
        auto *editor = settings.findChild<QKeySequenceEdit *>("activationShortcut");
        auto *apply = settings.findChild<QPushButton *>("applyActivationShortcut");
        QVERIFY(editor); QVERIFY(apply);
        editor->setKeySequence(QKeySequence("Ctrl+Alt+K")); apply->click();
        for (const QString &invalid : {QString(), QString("K"), QString("Shift+K"),
             QString("Ctrl+K, Ctrl+C"), QString("Ctrl+Alt+Shift+K"), QString("Ctrl+Escape")}) {
            editor->setKeySequence(QKeySequence(invalid)); apply->click();
            QCOMPARE(host.findChild<ShortcutManager *>()->currentSequence(), QKeySequence("Ctrl+Alt+K"));
            QVERIFY(settings.findChild<QLabel *>("activationShortcutStatus")->text().contains(QStringLiteral("未更改")));
        }
        QWidget restarted;
        pixiu::HostTray restored(&restarted);
        QCOMPARE(restarted.findChild<ShortcutManager *>()->currentSequence(), QKeySequence("Ctrl+Alt+K"));
    }
    void corruptSavedValueFallsBackWithoutOverwritingIt()
    {
        QSettings settings;
        settings.setValue("pixiu/activationShortcut", "K"); settings.sync();
        QWidget host;
        pixiu::HostTray tray(&host);
        QCOMPARE(host.findChild<ShortcutManager *>()->currentSequence(), QKeySequence("Ctrl+Alt+P"));
        QCOMPARE(QSettings().value("pixiu/activationShortcut").toString(), QString("K"));
    }
    void writeFailureDoesNotClaimPersistence()
    {
        QTemporaryFile notDirectory(config.path() + "/blocked-XXXXXX");
        QVERIFY(notDirectory.open());
        QSettings::setPath(QSettings::IniFormat, QSettings::UserScope, notDirectory.fileName());
        QWidget host;
        pixiu::HostTray tray(&host);
        pixiu::SettingsWorkspace settings(&host);
        auto *editor = settings.findChild<QKeySequenceEdit *>("activationShortcut");
        QVERIFY(editor);
        editor->setKeySequence(QKeySequence("Ctrl+Alt+K"));
        settings.findChild<QPushButton *>("applyActivationShortcut")->click();
        QCOMPARE(host.findChild<ShortcutManager *>()->currentSequence(), QKeySequence("Ctrl+Alt+K"));
        QVERIFY(settings.findChild<QLabel *>("activationShortcutStatus")->text().contains(QStringLiteral("保存失败")));
        QVERIFY(settings.hasUnsavedChanges());
    }
    void unappliedDraftUsesHostExitGuardWithoutSaving()
    {
        QWidget host;
        pixiu::HostTray tray(&host);
        pixiu::SettingsWorkspace settings(&host);
        pixiu::HostCloseGuard guard(&host);
        auto *editor = settings.findChild<QKeySequenceEdit *>("activationShortcut");
        QVERIFY(editor);
        editor->setKeySequence(QKeySequence("Ctrl+Alt+K"));
        QVERIFY(settings.hasUnsavedChanges());
        QTimer::singleShot(0, &host, [&]() {
            if (auto *box = host.findChild<QMessageBox *>())
                box->findChild<QPushButton *>("hostExitKeep")->click();
        });
        QVERIFY(!guard.confirmExit());
        QCOMPARE(editor->keySequence(), QKeySequence("Ctrl+Alt+K"));
        QTimer::singleShot(0, &host, [&]() {
            if (auto *box = host.findChild<QMessageBox *>())
                box->findChild<QPushButton *>("hostExitDiscard")->click();
        });
        QVERIFY(guard.confirmExit());
        QCOMPARE(host.findChild<ShortcutManager *>()->currentSequence(), QKeySequence("Ctrl+Alt+P"));
        QVERIFY(!QSettings().contains("pixiu/activationShortcut"));
    }
};
QTEST_MAIN(HostShortcutTest)
#include "t_host_shortcut.moc"
