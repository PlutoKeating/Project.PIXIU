#include <QTest>
#include <QWidget>
#include "app/ShortcutManager.h"
#include <kysdk/desktop/libkyshortcut.h>

static int createResult, updateResult, deletes;
static QString registeredName;
int kdk_shortcut_create_global_shortcut(const char *name, const char *, const char *)
{ registeredName = QString::fromUtf8(name); return createResult; }
int kdk_shortcut_set_global_shortcut(const char *, const char *, const char *) { return updateResult; }
int kdk_shortcut_delete_global_shortcut(const char *) { ++deletes; return KYSDK_SUCCESS; }

class TestShortcutKylin : public QObject
{
    Q_OBJECT
private slots:
    void init() { createResult = updateResult = KYSDK_SUCCESS; deletes = 0; }
    void ownsOnlySuccessfulRegistration()
    {
        QWidget host;
        {
            ShortcutManager manager(&host);
            QVERIFY(manager.registerToggleShortcut());
            QVERIFY(manager.isGlobal());
            QCOMPARE(registeredName, QStringLiteral("pixiu.activate"));
            QCOMPARE(deletes, 0);
            manager.releaseToggleShortcut();
            QVERIFY(!manager.isGlobal());
            QCOMPARE(deletes, 1);
        }
        QCOMPARE(deletes, 1);
    }
    void failedRegistrationDoesNotDeleteSomeoneElsesBinding()
    {
        QWidget host;
        createResult = KYSDK_SHORTCUT_EXISTED;
        updateResult = -2;
        {
            ShortcutManager manager(&host);
            QVERIFY(manager.registerToggleShortcut()); // Qt fallback
            QVERIFY(!manager.isGlobal());
        }
        QCOMPARE(deletes, 0);
    }
    void updatedRegistrationIsReleasedBeforeReplacement()
    {
        QWidget host;
        createResult = KYSDK_SHORTCUT_EXISTED;
        {
            ShortcutManager manager(&host);
            QVERIFY(manager.registerToggleShortcut());
            QVERIFY(manager.isGlobal());
            QVERIFY(manager.registerToggleShortcut());
            QCOMPARE(deletes, 1);
        }
        QCOMPARE(deletes, 2);
    }
};
QTEST_MAIN(TestShortcutKylin)
#include "t_shortcut_kylin.moc"
