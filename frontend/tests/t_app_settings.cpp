#include <QDir>
#include <QSettings>
#include <QTemporaryDir>
#include <QTest>

#include "app/AppSettings.h"

// AppSettings 持久化契约测试：使用独立的 Ini 配置目录，避免污染真实配置。
class TestAppSettings : public QObject
{
    Q_OBJECT

private slots:
    void initTestCase();
    void roundTripValues();
    void missingKeysReturnDefault();
    void keysAreStable();
    void cleanupTestCase();

private:
    QTemporaryDir m_tempDir;
};

void TestAppSettings::initTestCase()
{
    QVERIFY(m_tempDir.isValid());
    qApp->setOrganizationName(QStringLiteral("PixiuTests"));
    qApp->setApplicationName(QStringLiteral("app_settings"));
    QSettings::setDefaultFormat(QSettings::IniFormat);
    QSettings::setPath(QSettings::IniFormat, QSettings::UserScope, m_tempDir.path());
}

void TestAppSettings::roundTripValues()
{
    {
        AppSettings settings;
        settings.setValue(AppSettings::keyLastLaunched, QVariant::fromValue(qint64(1786164000)));
        settings.setValue(AppSettings::keyLanguage, QStringLiteral("zh_CN"));
        settings.sync();
        QVERIFY(settings.contains(AppSettings::keyLastLaunched));
        QVERIFY(!settings.fileName().isEmpty());
    }

    {
        AppSettings settings;
        QCOMPARE(settings.value(AppSettings::keyLastLaunched).toLongLong(),
                 qint64(1786164000));
        QCOMPARE(settings.value(AppSettings::keyLanguage).toString(),
                 QStringLiteral("zh_CN"));
    }
}

void TestAppSettings::missingKeysReturnDefault()
{
    AppSettings settings;
    QVERIFY(settings.value(AppSettings::keyBallPosition).isNull());
    QCOMPARE(settings.value(AppSettings::keyTheme, QStringLiteral("system")).toString(),
             QStringLiteral("system"));
}

void TestAppSettings::keysAreStable()
{
    QVERIFY(!AppSettings::keyLastLaunched.isEmpty());
    QVERIFY(!AppSettings::keyLanguage.isEmpty());
    QVERIFY(!AppSettings::keyTheme.isEmpty());
    QVERIFY(!AppSettings::keyWindowGeometry.isEmpty());
    QVERIFY(!AppSettings::keyBallPosition.isEmpty());
}

void TestAppSettings::cleanupTestCase()
{
    // 触发持久化，随后 QTemporaryDir 自动清理测试配置目录。
    AppSettings settings;
    settings.sync();
}

QTEST_MAIN(TestAppSettings)
#include "t_app_settings.moc"
