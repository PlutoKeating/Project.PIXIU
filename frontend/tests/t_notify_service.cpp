#include <QTest>

#include "services/NotifyService.h"

// NotifyService 无托盘环境（offscreen/headless）下的降级行为测试。
class TestNotifyService : public QObject
{
    Q_OBJECT

private slots:
    void unavailableByDefault();
    void notifyDegradesGracefullyWithoutTray();
    void notifyWithEmptyTextDoesNotCrash();
};

void TestNotifyService::unavailableByDefault()
{
    NotifyService service;
    QVERIFY(!service.isAvailable());
}

void TestNotifyService::notifyDegradesGracefullyWithoutTray()
{
    NotifyService service;
    QVERIFY(!service.notify(QStringLiteral("标题"), QStringLiteral("内容")));
}

void TestNotifyService::notifyWithEmptyTextDoesNotCrash()
{
    NotifyService service;
    service.notify(QString(), QString());
    QVERIFY(true);
}

QTEST_MAIN(TestNotifyService)
#include "t_notify_service.moc"
