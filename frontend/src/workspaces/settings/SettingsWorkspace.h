#pragma once
#include <QWidget>
#include <QPointer>
class QKeySequenceEdit;
namespace pixiu {
class HostTray;
class SettingsWorkspace : public QWidget
{
    Q_OBJECT
public:
    explicit SettingsWorkspace(QWidget *parent = nullptr);
    bool hasUnsavedChanges() const;
signals:
    void agentSettingsRequested();
private:
    QKeySequenceEdit *m_activationShortcut = nullptr;
    QPointer<HostTray> m_tray;
    bool m_shortcutSaveFailed = false;
};
}
