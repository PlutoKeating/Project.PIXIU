#include "HostWindowPin.h"
#include <QTest>
#include <QWidget>
#ifdef PIXIU_HAVE_KYSDK
#include <windowmanager/windowmanager.h>
#endif

class HostWindowPinTest : public QObject
{
    Q_OBJECT
private slots:
#ifdef PIXIU_HAVE_KYSDK
    void init() {
        kdk::WindowManager::entries.clear();
        kdk::WindowManager::requests = 0;
        kdk::WindowManager::requestedId.clear();
    }
    void nativeRequiresUniqueOwnedWindow() {
        QWidget host;
        host.setWindowTitle("PIXIU");
        pixiu::HostWindowPin pin(&host);
        QVERIFY(!pin.available());
        pin.setPinned(true);
        QCOMPARE(kdk::WindowManager::requests, 0);
        auto &entries = kdk::WindowManager::entries;
        entries.insert("foreign", {quint32(QCoreApplication::applicationPid() + 1), "PIXIU", {}});
        emit kdk::WindowManager::self()->windowAdded("foreign");
        QVERIFY(!pin.available());
        entries.insert("host", {quint32(QCoreApplication::applicationPid()), "PIXIU", {}});
        emit kdk::WindowManager::self()->windowAdded("host");
        QVERIFY(pin.available());
        entries.insert("duplicate", entries.value("host"));
        emit kdk::WindowManager::self()->windowAdded("duplicate");
        QVERIFY(!pin.available());
        pin.setPinned(true);
        QCOMPARE(kdk::WindowManager::requests, 0);
        entries.remove("duplicate");
        entries["host"].info.valid = false;
        emit kdk::WindowManager::self()->windowRemoved("duplicate");
        QVERIFY(!pin.available());
        entries["host"].info.valid = true;
        emit kdk::WindowManager::self()->windowChanged("host");
        QVERIFY(pin.available());
    }
    void nativeWaitsForFeedbackAndNeverRetriesToggle() {
        QWidget host;
        host.setWindowTitle("PIXIU");
        auto &entries = kdk::WindowManager::entries;
        entries.insert("host", {quint32(QCoreApplication::applicationPid()), "PIXIU", {}});
        pixiu::HostWindowPin pin(&host);
        QVERIFY(pin.available());
        pin.setPinned(true);
        QVERIFY(pin.pending());
        QVERIFY(!pin.pinned());
        QVERIFY(pin.status().contains(QStringLiteral("尚未报告成功")));
        QCOMPARE(kdk::WindowManager::requestedId.toString(), QString("host"));
        pin.setPinned(true);
        pin.setPinned(false);
        QCOMPARE(kdk::WindowManager::requests, 1);
        entries["host"].info.above = true;
        emit kdk::WindowManager::self()->keepAboveChanged("host");
        QVERIFY(pin.pinned());
        QVERIFY(!pin.pending());
        pin.setPinned(true);
        QCOMPARE(kdk::WindowManager::requests, 1);
        pin.setPinned(false);
        QCOMPARE(kdk::WindowManager::requests, 2);
        QVERIFY(pin.pinned());
        entries["host"].info.above = false;
        emit kdk::WindowManager::self()->keepAboveChanged("host");
        QVERIFY(!pin.pinned());
        QVERIFY(!pin.pending());
    }
    void nativeTimeoutDoesNotClaimSuccessOrMutateReplacement() {
        QWidget host;
        host.setWindowTitle("PIXIU");
        auto &entries = kdk::WindowManager::entries;
        entries.insert("host", {quint32(QCoreApplication::applicationPid()), "PIXIU", {}});
        pixiu::HostWindowPin pin(&host);
        pin.setPinned(true);
        QTRY_VERIFY_WITH_TIMEOUT(!pin.pending(), 3000);
        QVERIFY(!pin.pinned());
        QVERIFY(pin.status().contains(QStringLiteral("未确认")));
        QCOMPARE(kdk::WindowManager::requests, 1);
        pin.setPinned(true);
        entries.insert("replacement", entries.take("host"));
        emit kdk::WindowManager::self()->windowRemoved("host");
        QVERIFY(!pin.pending());
        QVERIFY(pin.status().contains(QStringLiteral("目标窗口已变化")));
        QCOMPARE(kdk::WindowManager::requests, 2);
    }
#else
    void compatiblePathPreservesHostVisibilityAndState_data() {
        QTest::addColumn<int>("state");
        QTest::addColumn<bool>("visible");
        QTest::newRow("hidden") << int(Qt::WindowNoState) << false;
        QTest::newRow("visible") << int(Qt::WindowNoState) << true;
        QTest::newRow("minimized") << int(Qt::WindowMinimized) << true;
        QTest::newRow("maximized") << int(Qt::WindowMaximized) << true;
        QTest::newRow("fullscreen") << int(Qt::WindowFullScreen) << true;
    }
    void compatiblePathPreservesHostVisibilityAndState() {
        QFETCH(int, state);
        QFETCH(bool, visible);
        QWidget host;
        host.setGeometry(100, 100, 500, 400);
        host.setWindowState(Qt::WindowStates(state));
        if (visible) host.show();
        const auto geometry = host.geometry();
        const auto flags = host.windowFlags();
        pixiu::HostWindowPin pin(&host);
        for (bool requested : {true, true, false, false}) {
            pin.setPinned(requested);
            QCOMPARE(pin.pinned(), requested);
            QCOMPARE(host.isVisible(), visible);
            QCOMPARE(host.windowState() & ~Qt::WindowActive, Qt::WindowStates(state));
            QCOMPARE(host.windowFlags() & ~Qt::WindowStaysOnTopHint, flags & ~Qt::WindowStaysOnTopHint);
            if (state == int(Qt::WindowNoState)) QCOMPARE(host.geometry(), geometry);
            QVERIFY(pin.status().contains(QStringLiteral("Qt 兼容路径")));
        }
    }
#endif
};
QTEST_MAIN(HostWindowPinTest)
#include "t_host_window_pin.moc"
