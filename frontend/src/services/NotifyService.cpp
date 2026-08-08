#include "services/NotifyService.h"

#include <QLoggingCategory>
#include <QSystemTrayIcon>

#ifdef PIXIU_HAVE_KYSDK
#include <kysdk/desktop/knotifier.h>
#endif

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
#ifdef PIXIU_HAVE_KYSDK
    // kysdk-notification：不依赖托盘，首次使用时创建通知器。
    if (!m_notifier) {
        m_notifier = new kdk::KNotifier(this);
        m_notifier->setAppName(QStringLiteral("PIXIU"));
        m_notifier->setAppIcon(QStringLiteral("dialog-information"));
        m_notifier->setShowTime(kNotificationTimeoutMs);
    }
    m_notifier->setSummary(title);
    m_notifier->setBodyText(body);
    const uint id = m_notifier->notify();
    qCInfo(lcNotify) << "kysdk notification sent, id:" << id;
    return true;
#else
    if (m_tray && m_tray->isVisible()) {
        m_tray->showMessage(title, body, QSystemTrayIcon::Information,
                            kNotificationTimeoutMs);
        return true;
    }

    // 托盘不可用：降级为日志，保证无桌面环境不阻塞、不崩溃。
    qCInfo(lcNotify) << "notification (degraded):" << title << "-" << body;
    return false;
#endif
}

bool NotifyService::isAvailable() const
{
#ifdef PIXIU_HAVE_KYSDK
    // kysdk-notification 无需托盘即可弹出系统通知。
    return true;
#else
    return m_tray != nullptr && m_tray->isVisible();
#endif
}
