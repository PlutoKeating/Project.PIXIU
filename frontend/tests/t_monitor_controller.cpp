#include <QSettings>
#include <QSignalSpy>
#include <QTemporaryDir>
#include <QTest>

#include "app/AppSettings.h"
#include "app/MonitorController.h"

// MonitorController：默认态、开关持久化、目录清单、本地活动日志。
class TestMonitorController : public QObject
{
    Q_OBJECT

private slots:
    void initTestCase();
    void defaultsAreOff();
    void enablePersistsAcrossInstances();
    void sourceTogglePersistsAndEmits();
    void directoriesRoundTrip();
    void logRecordsToggles();
    void cleanupTestCase();

private:
    QTemporaryDir m_tempDir;
};

void TestMonitorController::initTestCase()
{
    QVERIFY(m_tempDir.isValid());
    qApp->setOrganizationName(QStringLiteral("PixiuTests"));
    qApp->setApplicationName(QStringLiteral("monitor_controller"));
    QSettings::setDefaultFormat(QSettings::IniFormat);
    QSettings::setPath(QSettings::IniFormat, QSettings::UserScope,
                       m_tempDir.path());
}

void TestMonitorController::defaultsAreOff()
{
    MonitorController controller(new AppSettings(this));
    QVERIFY(!controller.isEnabled());
    for (int i = 0; i < 4; ++i) {
        QVERIFY(!controller.isSourceEnabled(static_cast<MonitorSource>(i)));
    }
    QVERIFY(controller.directories().isEmpty());
    QCOMPARE(controller.log().size(), 0);
}

void TestMonitorController::enablePersistsAcrossInstances()
{
    {
        AppSettings settings;
        MonitorController controller(&settings);
        QSignalSpy spy(&controller, &MonitorController::enabledChanged);
        controller.setEnabled(true);
        QCOMPARE(spy.count(), 1);
        QCOMPARE(spy.takeFirst().at(0).toBool(), true);
    }
    AppSettings settings;
    MonitorController reloaded(&settings);
    QVERIFY(reloaded.isEnabled());
    QCOMPARE(reloaded.log().size(), 0); // 日志不持久化，重启从零开始
}

void TestMonitorController::sourceTogglePersistsAndEmits()
{
    {
        AppSettings settings;
        MonitorController controller(&settings);
        controller.setEnabled(true);
        QSignalSpy spy(&controller, &MonitorController::sourceChanged);
        controller.setSourceEnabled(MonitorSource::Directory, true);
        QCOMPARE(spy.count(), 1);
    }
    AppSettings settings;
    MonitorController reloaded(&settings);
    QVERIFY(reloaded.isSourceEnabled(MonitorSource::Directory));
    QVERIFY(!reloaded.isSourceEnabled(MonitorSource::Clipboard));
}

void TestMonitorController::directoriesRoundTrip()
{
    AppSettings settings;
    MonitorController controller(&settings);
    QSignalSpy spy(&controller, &MonitorController::directoriesChanged);
    controller.setDirectories({QStringLiteral("/home/u/Downloads"),
                               QStringLiteral("/home/u/wxfiles")});
    QCOMPARE(spy.count(), 1);
    QCOMPARE(controller.directories().size(), 2);

    AppSettings settings2;
    MonitorController reloaded(&settings2);
    QCOMPARE(reloaded.directories().size(), 2);
    QCOMPARE(reloaded.directories().first(),
             QStringLiteral("/home/u/Downloads"));
}

void TestMonitorController::logRecordsToggles()
{
    // 隔离：清除前序用例（enablePersistsAcrossInstances 等）在同一配置文件
    // 中持久化的开关状态，确保本用例从默认态出发、每步变更都产生日志。
    {
        QSettings raw;
        raw.clear();
    }
    AppSettings settings;
    MonitorController controller(&settings);
    controller.setEnabled(true);
    controller.setSourceEnabled(MonitorSource::Clipboard, true);
    controller.appendLog(QStringLiteral("手动条目"));
    QCOMPARE(controller.log().size(), 3);
    QVERIFY(controller.log().last().text ==
            QStringLiteral("手动条目"));
    // 开关产生的日志时间戳有效
    QVERIFY(controller.log().first().timestamp > 0);
}

void TestMonitorController::cleanupTestCase()
{
    AppSettings settings;
    settings.sync();
}

QTEST_MAIN(TestMonitorController)
#include "t_monitor_controller.moc"
