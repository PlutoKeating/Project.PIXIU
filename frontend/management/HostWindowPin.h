#pragma once
#include <QObject>
#include <QTimer>
#include <QVariant>

class QWidget;
namespace pixiu {
// Controls only the existing host; never owns another window or settings store.
class HostWindowPin : public QObject
{
    Q_OBJECT
public:
    explicit HostWindowPin(QWidget *host);
    bool available() const { return m_available; }
    bool pinned() const { return m_pinned; }
    bool pending() const { return m_timeout.isActive(); }
    QString status() const;
    void setPinned(bool pinned);
signals:
    void changed();
private:
    void refresh();
    QWidget *m_host;
    QVariant m_windowId;
    QTimer m_timeout;
    bool m_available = false;
    bool m_pinned = false;
    bool m_requested = false;
    QString m_error;
};
}
