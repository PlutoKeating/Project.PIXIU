#include "services/NotifyService.h"

#include <QLoggingCategory>
#include <QSystemTrayIcon>

Q_LOGGING_CATEGORY(lcNotify, "pixiu.notify")

namespace {
constexpr int kNotificationTimeoutMs = 5000;
}

NotifyService::NotifyService(QObject *parent)
    : QObject(parent)
{
}

void NotifyService::setTrayIcon(QSystemTrayIcon *tray)
{
    m_tray = tray;
}

bool NotifyService::notify(const QString &title, const QString &body)
{
    if (m_tray && m_tray->isVisible()) {
        m_tray->showMessage(title, body, QSystemTrayIcon::Information,
                            kNotificationTimeoutMs);
        return true;
    }

    // 托盘不可用：降级为日志，保证无桌面环境不阻塞、不崩溃。
    qCInfo(lcNotify) << "notification (degraded):" << title << "-" << body;
    return false;
}

bool NotifyService::isAvailable() const
{
    return m_tray != nullptr && m_tray->isVisible();
}
