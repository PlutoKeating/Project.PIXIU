#pragma once

#ifdef QT_WIDGETS_LIB
#include <QApplication>
#else
#include <QCoreApplication>
#endif
#include <QDir>
#include <QFile>
#include <QStandardPaths>
#include <QTemporaryDir>
#include <QTest>

// Establish ownership before QApplication or any test can resolve/cache temp paths.
// The directory outlives the application, controllers and their asynchronous work.
template<class Test>
int runIsolatedUpgradeTest(int argc, char **argv)
{
    QTemporaryDir temporary(QDir::tempPath() + QStringLiteral("/pixiu-upgrade-test-XXXXXX"));
    if (!temporary.isValid()
        || !qputenv("TMPDIR", QFile::encodeName(temporary.path()))) {
        qCritical("Cannot create private upgrade test directory; refusing to run");
        return 2;
    }
#ifdef QT_WIDGETS_LIB
    QApplication application(argc, argv);
#else
    QCoreApplication application(argc, argv);
#endif
    if (QDir::cleanPath(QStandardPaths::writableLocation(QStandardPaths::TempLocation))
        != QDir::cleanPath(temporary.path())) {
        qCritical("Qt did not adopt private upgrade test directory; refusing to run");
        return 2;
    }
    Test test;
    return QTest::qExec(&test, argc, argv);
}
