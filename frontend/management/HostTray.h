#pragma once
#include <QObject>
#include <QElapsedTimer>
#include <QKeySequence>

class QWidget;
class NotifyService;
class ShortcutManager;
namespace pixiu {
// An optional entry to the existing host, never a second application/window.
class HostTray : public QObject
{
    Q_OBJECT
public:
    explicit HostTray(QWidget *host);
    void notifyConflict();
    void notifyPreferences(int count);
    QKeySequence activationShortcut() const;
    QString shortcutStatus() const;
    // Empty result means applied and saved; otherwise return an explicit error.
    QString setActivationShortcut(const QKeySequence &sequence);
signals:
    void shortcutChanged();
private:
    NotifyService *m_notify;
    ShortcutManager *m_shortcut;
    QString m_shortcutWarning;
    QElapsedTimer m_lastPreferenceNotice;
};
}
