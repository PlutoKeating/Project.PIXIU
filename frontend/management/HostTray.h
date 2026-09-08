#pragma once
#include <QObject>

class QWidget;
class NotifyService;
namespace pixiu {
// An optional entry to the existing host, never a second application/window.
class HostTray : public QObject
{
    Q_OBJECT
public:
    explicit HostTray(QWidget *host);
    void notifyConflict();
private:
    NotifyService *m_notify;
};
}
