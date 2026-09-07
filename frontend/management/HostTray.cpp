#include "HostTray.h"
#include <QAction>
#include <QMenu>
#include <QSystemTrayIcon>
#include <QWidget>

namespace pixiu {
HostTray::HostTray(QWidget *host) : QObject(host)
{
    auto *tray = new QSystemTrayIcon(host->windowIcon(), this);
    tray->setToolTip(tr("PIXIU — 记忆工作台"));
    auto *menu = new QMenu(host);
    auto *show = menu->addAction(tr("显示 PIXIU"));
    show->setObjectName(QStringLiteral("hostTrayShow"));
    auto *quit = menu->addAction(tr("退出 PIXIU"));
    quit->setObjectName(QStringLiteral("hostTrayQuit"));
    auto restore = [host]() {
        host->setWindowState(host->windowState() & ~Qt::WindowMinimized);
        host->show();
        host->raise();
        host->activateWindow();
    };
    connect(show, &QAction::triggered, this, restore);
    connect(quit, &QAction::triggered, this, [host, restore]() {
        restore();
        host->close(); // HostCloseGuard owns pending work and unsaved draft checks.
    });
    connect(tray, &QSystemTrayIcon::activated, this, [restore](QSystemTrayIcon::ActivationReason reason) {
        if (reason == QSystemTrayIcon::Trigger || reason == QSystemTrayIcon::DoubleClick) restore();
    });
    tray->setContextMenu(menu);
    if (QSystemTrayIcon::isSystemTrayAvailable()) tray->show();
    // Closing the last window still exits. No invisible fallback background app.
}
}
