#include "app/PixiuApp.h"

#include "app/SingleInstanceGuard.h"
#include "app/TrayIcon.h"
#include "app/AppSettings.h"

#include <QLoggingCategory>
#include <QCoreApplication>
#include <QDateTime>

Q_LOGGING_CATEGORY(lcApp, "pixiu.app")

// 私有实现：后续 feature（单实例、托盘、设置、服务与窗口）在此挂载。
struct PixiuApp::Private
{
    // Phase 1B 暂无成员；后续以 QScopedPointer 持有服务与窗口对象。
};

PixiuApp::PixiuApp(QObject *parent)
    : QObject(parent)
    , d(new Private())
{
}

PixiuApp::~PixiuApp() = default;

bool PixiuApp::start()
{
    qCInfo(lcApp) << "PIXIU application starting";

    // 单实例守护：重复启动时请求唤起已有实例并让本进程退出。
    m_instanceGuard = new SingleInstanceGuard(this);
    if (!m_instanceGuard->tryStart()) {
        qCInfo(lcApp) << "exiting: another instance is already running";
        return false;
    }
    connect(m_instanceGuard, &SingleInstanceGuard::activationRequested, this, []() {
        qCInfo(lcApp) << "activation requested; main window will be raised (Phase 2+)";
    });

    // 系统托盘：打开主入口 + 显式退出。
    m_tray = new TrayIcon(this);
    if (m_tray->show()) {
        connect(m_tray, &TrayIcon::openRequested, this, []() {
            qCInfo(lcApp) << "open requested; main window will be shown (Phase 2+)";
        });
        connect(m_tray, &TrayIcon::quitRequested, this, &PixiuApp::shutdown);
        connect(m_tray, &TrayIcon::quitRequested, QCoreApplication::quit);
    } else {
        m_tray->deleteLater();
        m_tray = nullptr;
    }

    // 基础设置持久化：记录最近一次启动时间，验证读写链路。
    m_settings = new AppSettings(this);
    const qint64 lastLaunched =
        m_settings->value(AppSettings::keyLastLaunched, QVariant::fromValue(qint64(0))).toLongLong();
    if (lastLaunched > 0) {
        qCInfo(lcApp) << "previous launch timestamp:" << lastLaunched;
    }
    m_settings->setValue(AppSettings::keyLastLaunched,
                         QDateTime::currentSecsSinceEpoch());
    m_settings->sync();

    // 后续 feature 在此创建服务与窗口（以 this 为 parent）。

    emit started();
    qCInfo(lcApp) << "PIXIU application started";
    return true;
}

void PixiuApp::shutdown()
{
    qCInfo(lcApp) << "PIXIU application shutting down";
    if (m_instanceGuard) {
        m_instanceGuard->stop();
    }
    emit aboutToShutdown();
}
