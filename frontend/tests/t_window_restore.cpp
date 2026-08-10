#include <QApplication>
#include <QGuiApplication>
#include <QScreen>
#include <QTemporaryDir>
#include <QTest>

#include "app/AppSettings.h"
#include "app/PixiuApp.h"
#include "widgets/ChatWindow.h"

// 窗口位置恢复回归：显示器分辨率/数量变化后，上次保存的位置可能整体位于
// 屏外（例如从大屏切到小屏）。恢复时必须钳制到当前可用屏幕区域内，否则
// 聊天框完全不可见，快捷入口（记忆/设置/导入/同步）点击自然全部失效。
class TestWindowRestore : public QObject
{
    Q_OBJECT

private slots:
    void initTestCase();
    void cleanupTestCase();
    void offScreenSavedGeometryRestoresInsideVisibleArea();

private:
    PixiuApp *m_app = nullptr;
    ChatWindow *m_chatWindow = nullptr;
    QTemporaryDir *m_configDir = nullptr;
};

void TestWindowRestore::initTestCase()
{
    // 与 main.cpp 相同的应用标识，并把 QSettings 隔离到临时目录，
    // 避免测试读写用户真实配置。
    QCoreApplication::setOrganizationName(QStringLiteral("Project.PIXIU"));
    QCoreApplication::setApplicationName(QStringLiteral("PIXIU"));
    QCoreApplication::setApplicationVersion(QStringLiteral("0.1.0"));
    m_configDir = new QTemporaryDir();
    QVERIFY(m_configDir->isValid());
    qputenv("XDG_CONFIG_HOME", m_configDir->path().toUtf8());
    // 单实例守卫的 socket 以 USER 命名；测试里隔离 USER，避免与桌面上正在
    // 运行的 PIXIU 实例互抢主实例（不影响被测代码路径）。
    qputenv("USER", QStringLiteral("pixiu-restore-test-%1")
                        .arg(QCoreApplication::applicationPid())
                        .toUtf8());

    // 预先写入一个明显位于屏外的保存位置（模拟大屏上的旧几何）。
    AppSettings settings;
    settings.setValue(AppSettings::keyWindowGeometry,
                      QRect(50000, 50000, 380, 640));
    settings.sync();

    m_app = new PixiuApp();
    QVERIFY(m_app->start());
    const auto windows = QApplication::topLevelWidgets();
    for (QWidget *w : windows) {
        if (ChatWindow *chat = qobject_cast<ChatWindow *>(w)) {
            m_chatWindow = chat;
            break;
        }
    }
    QVERIFY(m_chatWindow != nullptr);
}

void TestWindowRestore::cleanupTestCase()
{
    if (m_app) {
        m_app->shutdown();
        delete m_app;
        m_app = nullptr;
    }
    delete m_configDir;
    m_configDir = nullptr;
}

void TestWindowRestore::offScreenSavedGeometryRestoresInsideVisibleArea()
{
    QRect area;
    const auto screens = QGuiApplication::screens();
    QVERIFY(!screens.isEmpty());
    for (QScreen *screen : screens) {
        area = area.united(screen->availableGeometry());
    }

    const QRect geo = m_chatWindow->geometry();
    // 窗口左上角必须落在可用区域内（允许窗口比屏幕高时顶部贴齐屏幕顶部）。
    QVERIFY(geo.left() >= area.left());
    QVERIFY(geo.left() <= area.right());
    QVERIFY(geo.top() >= area.top());
    QVERIFY(geo.top() <= area.bottom());
    // 且不再停留在屏外的原始保存位置。
    QVERIFY(geo.left() < 50000);
    QVERIFY(geo.top() < 50000);
    // 窗口与屏幕可用区域必须相交（至少部分可见、入口可点）。
    QVERIFY(geo.intersects(area));
}

QTEST_MAIN(TestWindowRestore)
#include "t_window_restore.moc"
