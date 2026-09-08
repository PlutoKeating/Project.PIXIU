#include "HostTray.h"
#include "app/ShortcutManager.h"
#include "services/NotifyService.h"
#include <QAction>
#include <QMenu>
#include <QSystemTrayIcon>
#include <QWidget>

namespace pixiu {
HostTray::HostTray(QWidget *host) : QObject(host)
{
    auto *tray = new QSystemTrayIcon(host->windowIcon(), this);
    m_notify = new NotifyService(this);
    m_notify->setTrayIcon(tray);
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
    auto *shortcut = new ShortcutManager(host, this);
    connect(shortcut, &ShortcutManager::toggleRequested, this, restore);
    shortcut->registerToggleShortcut();
    show->setText(shortcut->isGlobal() ? tr("显示 PIXIU（Ctrl+Alt+P，全局）")
                                    : tr("显示 PIXIU（Ctrl+Alt+P，仅应用内）"));
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
void HostTray::notifyConflict()
{
    m_notify->notify(tr("PIXIU 冲突提醒"),
        tr("检测到高严重度记忆冲突，请打开“记忆 → 偏好与审计”核对。此提醒不会执行修改或删除。"));
}
}
