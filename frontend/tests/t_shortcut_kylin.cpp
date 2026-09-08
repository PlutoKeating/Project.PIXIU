#include <QTest>
#include <QWidget>
#include "app/ShortcutManager.h"
#include <kysdk/desktop/libkyshortcut.h>

static int createResult, updateResult, deletes, legacyDeletes, legacyResult;
static QStringList calls;
static QString registeredName;
int kdk_shortcut_create_global_shortcut(const char *name, const char *, const char *)
{ calls << QStringLiteral("create"); registeredName = QString::fromUtf8(name); return createResult; }
int kdk_shortcut_set_global_shortcut(const char *, const char *, const char *) { return updateResult; }
int kdk_shortcut_delete_global_shortcut(const char *name)
{
    if (QString::fromUtf8(name) == QStringLiteral("pixiu-frontend.toggle-chat")) {
        calls << QStringLiteral("remove-legacy");
        ++legacyDeletes;
        return legacyResult;
    }
    Q_ASSERT(QString::fromUtf8(name) == QStringLiteral("pixiu.activate"));
    ++deletes;
    return KYSDK_SUCCESS;
}

class TestShortcutKylin : public QObject
{
    Q_OBJECT
private slots:
    void init() {
        createResult = updateResult = legacyResult = KYSDK_SUCCESS;
        deletes = legacyDeletes = 0;
        calls.clear();
    }
    void removesLegacyBindingBeforeRegisteringReplacement()
    {
        QWidget host;
        ShortcutManager manager(&host);
        QVERIFY(manager.registerToggleShortcut());
        QCOMPARE(calls, QStringList({QStringLiteral("remove-legacy"), QStringLiteral("create")}));
        manager.releaseToggleShortcut();
        QCOMPARE(legacyDeletes, 1);
    }
    void legacyCleanupFailureDoesNotBlockNewRegistration()
    {
        legacyResult = -3;
        QWidget host;
        ShortcutManager manager(&host);
        QVERIFY(manager.registerToggleShortcut());
        QVERIFY(manager.isGlobal());
        QCOMPARE(legacyDeletes, 1);
        QCOMPARE(registeredName, QStringLiteral("pixiu.activate"));
    }
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
