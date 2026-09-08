#include "HostWindowPin.h"
#include <QCoreApplication>
#include <QWidget>
#ifdef PIXIU_HAVE_KYSDK
#include <windowmanager/windowmanager.h>
#endif

namespace pixiu {
HostWindowPin::HostWindowPin(QWidget *host) : QObject(host), m_host(host)
{
    m_timeout.setSingleShot(true);
    m_timeout.setInterval(2000);
    connect(&m_timeout, &QTimer::timeout, this, [this]() {
        refresh();
        if (!m_available || m_pinned != m_requested)
            m_error = tr("窗口管理器未确认请求，未自动重试。请核对当前状态。");
        emit changed();
    });
#ifdef PIXIU_HAVE_KYSDK
    auto *manager = kdk::WindowManager::self();
    auto update = [this]() { refresh(); };
    connect(manager, &kdk::WindowManager::windowAdded, this, update);
    connect(manager, &kdk::WindowManager::windowRemoved, this, update);
    connect(manager, &kdk::WindowManager::windowChanged, this, update);
    connect(manager, &kdk::WindowManager::keepAboveChanged, this, update);
    connect(manager, &kdk::WindowManager::titleChanged, this, update);
#endif
    connect(host, &QWidget::windowTitleChanged, this, [this]() { refresh(); });
    refresh();
}
void HostWindowPin::refresh()
{
#ifdef PIXIU_HAVE_KYSDK
    QVariant target;
    int matches = 0;
    // Wayland uses compositor IDs, not QWidget::winId(). Never select the
    // desktop's active window or merely the first window belonging to this PID.
    for (const auto &id : kdk::WindowManager::windows()) {
        if (kdk::WindowManager::getPid(id) == quint32(QCoreApplication::applicationPid())
            && kdk::WindowManager::getWindowTitle(id) == m_host->windowTitle()) {
            target = id;
            ++matches;
        }
    }
    m_available = false;
    if (matches == 1 && !m_host->windowTitle().isEmpty()) {
        const auto info = kdk::WindowManager::getwindowInfo(target);
        m_available = info.isValid();
        if (m_available) m_pinned = info.isKeepAbove();
    }
    if (pending() && target != m_windowId) {
        m_timeout.stop();
        m_error = tr("目标窗口已变化，未对新窗口重试。");
    }
    m_windowId = m_available ? target : QVariant();
    if (pending() && m_available && m_pinned == m_requested) m_timeout.stop();
#else
    m_available = true;
    m_pinned = m_host->windowFlags().testFlag(Qt::WindowStaysOnTopHint);
#endif
    emit changed();
}
QString HostWindowPin::status() const
{
    if (!m_error.isEmpty()) return m_error;
    if (!m_available) return tr("无法唯一识别主窗口，未更改置顶状态。");
    if (pending()) return tr("正在等待窗口管理器确认；尚未报告成功。");
#ifdef PIXIU_HAVE_KYSDK
    return m_pinned ? tr("麒麟窗口管理器：已置顶。") : tr("麒麟窗口管理器：未置顶。");
#else
    return m_pinned ? tr("已请求置顶（Qt 兼容路径）；实际效果取决于窗口管理器。")
                    : tr("未请求置顶（Qt 兼容路径）；不代表麒麟 SDK 验收。");
#endif
}
void HostWindowPin::setPinned(bool pinned)
{
    if (pending()) return; // The SDK toggles; never retry an in-flight request.
    m_error.clear();
    refresh();
    if (!m_available || m_pinned == pinned) return;
#ifdef PIXIU_HAVE_KYSDK
    m_requested = pinned;
    m_timeout.start();
    emit changed();
    kdk::WindowManager::keepWindowAbove(m_windowId);
#else
    const bool visible = m_host->isVisible();
    const auto state = m_host->windowState();
    const auto geometry = m_host->geometry();
    m_host->setWindowFlag(Qt::WindowStaysOnTopHint, pinned);
    m_host->setGeometry(geometry);
    m_host->setWindowState(state);
    if (visible) m_host->show();
    refresh();
#endif
}
}
