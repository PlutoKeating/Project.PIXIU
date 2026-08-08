#include "app/PixiuApp.h"

#include "app/SingleInstanceGuard.h"
#include "app/TrayIcon.h"
#include "app/AppSettings.h"
#include "widgets/FloatingBall.h"
#include "widgets/ChatWindow.h"

#include <QLoggingCategory>
#include <QCoreApplication>
#include <QDateTime>
#include <QGuiApplication>
#include <QScreen>

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

    // 系统托盘：打开主入口 + 显式退出。
    m_tray = new TrayIcon(this);
    if (m_tray->show()) {
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

    // 悬浮球：常驻桌面入口（默认屏幕右下角；位置持久化在下一 feature）。
    m_floatingBall = new FloatingBall();
    const QVariant savedPos = m_settings->value(AppSettings::keyBallPosition);
    if (savedPos.isValid()) {
        m_floatingBall->restorePosition(savedPos.toPoint());
    } else if (QScreen *screen = QGuiApplication::primaryScreen()) {
        const QRect screenRect = screen->availableGeometry();
        m_floatingBall->move(screenRect.right() - m_floatingBall->width() - 24,
                             screenRect.bottom() - m_floatingBall->height() - 24);
    }
    connect(m_floatingBall, &FloatingBall::movedTo, this, [this](const QPoint &pos) {
        m_settings->setValue(AppSettings::keyBallPosition, pos);
        m_settings->sync();
    });
    m_floatingBall->show();

    // 聊天主窗口：默认屏幕右下角弹出（悬浮球附近）。
    m_chatWindow = new ChatWindow();
    if (QScreen *screen = QGuiApplication::primaryScreen()) {
        const QRect screenRect = screen->availableGeometry();
        m_chatWindow->move(screenRect.right() - m_chatWindow->width() - 24,
                           screenRect.bottom() - m_chatWindow->height() - 24);
    }

    // 各入口统一唤起聊天框。
    connect(m_floatingBall, &FloatingBall::clicked, this, [this]() {
        if (m_chatWindow->isChatVisible()) {
            m_chatWindow->hideAnimated();
        } else {
            m_chatWindow->showAndFocus();
        }
    });
    connect(m_chatWindow, &ChatWindow::closeRequested,
            m_chatWindow, &ChatWindow::hideAnimated);
    connect(m_chatWindow, &ChatWindow::openPanelRequested, this, []() {
        qCInfo(lcApp) << "memory panel requested (Phase 5)";
    });
    connect(m_instanceGuard, &SingleInstanceGuard::activationRequested,
            m_chatWindow, &ChatWindow::showAndFocus);
    if (m_tray) {
        connect(m_tray, &TrayIcon::openRequested,
                m_chatWindow, &ChatWindow::showAndFocus);
    }

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
