#pragma once
#include <QWidget>
class BackendTransport;
class QCheckBox;
class QLabel;
class QListWidget;
class QPushButton;
namespace pixiu {
class DevicePage : public QWidget
{
    Q_OBJECT
public:
    explicit DevicePage(QWidget *parent, BackendTransport *transport = nullptr);
private:
    enum class Pending { None, Status, Peers, Discover, Settings, Revoke };
    void controls();
    void finish(const QString &message);
    void refresh();
    BackendTransport *m_transport;
    QCheckBox *m_enabled, *m_paused;
    QLabel *m_status, *m_summary;
    QListWidget *m_peers, *m_discovered;
    QPushButton *m_refresh, *m_save, *m_discover, *m_revoke;
    Pending m_pending = Pending::None;
    bool m_loaded = false;
    QString m_revoking;
};
}
