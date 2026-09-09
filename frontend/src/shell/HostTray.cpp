#include "HostTray.h"
#include "HostWindowPin.h"
#include "app/ShortcutManager.h"
#include "services/NotifyService.h"
#include <QAction>
#include <QGuiApplication>
#include <QMenu>
#include <QScreen>
#include <QSettings>
#include <QSystemTrayIcon>
#include <QWidget>

namespace pixiu {
namespace {
const char shortcutKey[] = "pixiu/activationShortcut";
bool validShortcut(const QKeySequence &sequence)
{
    if (sequence.count() != 1) return false;
    const int chord = sequence[0];
    const int key = chord & ~Qt::KeyboardModifierMask;
    const int modifiers = chord & Qt::KeyboardModifierMask;
    const int allowed = Qt::CTRL | Qt::ALT | Qt::SHIFT | Qt::META;
    int count = 0;
    for (int modifier : {Qt::CTRL, Qt::ALT, Qt::SHIFT, Qt::META})
        if (modifiers & modifier) ++count;
    // Match the SDK's single character + 1–2 modifiers contract. Avoid plain
    // typing/Shift-only bindings and reject multi-chord Qt sequences.
    return !(modifiers & ~allowed) && count >= 1 && count <= 2
        && (modifiers & (Qt::CTRL | Qt::ALT | Qt::META))
        && ((key >= Qt::Key_A && key <= Qt::Key_Z) || (key >= Qt::Key_0 && key <= Qt::Key_9));
}
}
HostTray::HostTray(QWidget *host) : QObject(host)
{
    new HostWindowPin(host);
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
        if (!host->isMaximized() && !host->isFullScreen()) {
            const QRect frame = host->frameGeometry();
            // Keep a usable title/header area on one real screen, not merely
            // inside the bounding rectangle of a disconnected monitor layout.
            const QRect handle(frame.topLeft(), QSize(qMin(160, frame.width()), qMin(32, frame.height())));
            bool reachable = false;
            for (auto *screen : QGuiApplication::screens())
                reachable |= screen->availableGeometry().contains(handle);
            if (!reachable) {
                if (auto *screen = QGuiApplication::primaryScreen())
                    host->move(screen->availableGeometry().topLeft());
            }
        }
        host->raise();
        host->activateWindow();
    };
    connect(show, &QAction::triggered, this, restore);
    m_shortcut = new ShortcutManager(host, this);
    connect(m_shortcut, &ShortcutManager::toggleRequested, this, restore);
    auto updateShortcutLabel = [this, show]() {
        show->setText(tr("显示 PIXIU（%1，%2）")
            .arg(activationShortcut().toString(QKeySequence::NativeText),
                 m_shortcut->isGlobal() ? tr("全局") : tr("仅应用内")));
    };
    connect(m_shortcut, &ShortcutManager::availabilityChanged, this, &HostTray::shortcutChanged);
    connect(this, &HostTray::shortcutChanged, this, updateShortcutLabel);
    const QString saved = QSettings().value(QString::fromLatin1(shortcutKey), "Ctrl+Alt+P").toString();
    const QKeySequence requested = QKeySequence::fromString(saved.left(64), QKeySequence::PortableText);
    const bool valid = saved.size() <= 64 && validShortcut(requested);
    if (!valid) m_shortcutWarning = tr("保存的快捷键无效，本次使用默认值；原配置未覆盖。");
    m_shortcut->registerToggleShortcut(valid ? requested : QKeySequence("Ctrl+Alt+P"));
    updateShortcutLabel();
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
QKeySequence HostTray::activationShortcut() const
{
    return m_shortcut->currentSequence();
}
QString HostTray::shortcutStatus() const
{
    return tr("当前：%1（%2）。%3").arg(activationShortcut().toString(QKeySequence::NativeText),
        m_shortcut->isGlobal() ? tr("全局") : tr("仅应用内；全局服务未就绪或注册失败"), m_shortcutWarning);
}
QString HostTray::setActivationShortcut(const QKeySequence &sequence)
{
    if (!validShortcut(sequence))
        return tr("未更改：请使用单组字母或数字，搭配 1～2 个控制键，且包含 Ctrl、Alt 或 Meta。");
    const auto previous = activationShortcut();
    if (!m_shortcut->registerToggleShortcut(sequence)) {
        m_shortcut->registerToggleShortcut(previous);
        emit shortcutChanged();
        return tr("注册失败，未保存新配置；请核对当前快捷键状态。");
    }
    QSettings settings;
    settings.setValue(QString::fromLatin1(shortcutKey), sequence.toString(QKeySequence::PortableText));
    settings.sync();
    m_shortcutWarning = settings.status() == QSettings::NoError ? QString()
        : tr("配置保存失败：当前会话已应用，重启后不保证保留。");
    emit shortcutChanged();
    return m_shortcutWarning;
}
void HostTray::notifyConflict()
{
    m_notify->notify(tr("PIXIU 冲突提醒"),
        tr("检测到高严重度记忆冲突，请打开“记忆 → 偏好与审计”核对。此提醒不会执行修改或删除。"));
}
void HostTray::notifyPreferences(int count)
{
    if (count < 1 || (m_lastPreferenceNotice.isValid() && m_lastPreferenceNotice.elapsed() < 60000)) return;
    m_lastPreferenceNotice.start();
    m_notify->notify(tr("PIXIU 偏好变化提醒"),
        tr("偏好列表出现新增记录或版本变化，请打开“记忆 → 偏好与审计”核对。此提醒不会修改偏好。"));
}
}
