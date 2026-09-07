#pragma once
#include <QWidget>
#include <QJsonObject>
class BackendTransport;
class QCheckBox;
class QPlainTextEdit;
class QPushButton;
class QLabel;
class QListWidget;
namespace pixiu {
class PrivacyPage : public QWidget
{
    Q_OBJECT
public:
    explicit PrivacyPage(QWidget *parent, BackendTransport *transport = nullptr);
    bool hasPendingOperation() const { return m_pending != Pending::None; }
    bool hasUnsavedChanges() const;
private:
    enum class Pending { None, Load, Save, Logs };
    void controls();
    void loadLogs(int offset);
    BackendTransport *m_transport;
    QCheckBox *m_enabled, *m_directory, *m_behavior;
    QPlainTextEdit *m_directories;
    QPushButton *m_load, *m_save, *m_logs, *m_previous, *m_next;
    QLabel *m_status;
    QListWidget *m_events;
    QJsonObject m_config;
    Pending m_pending = Pending::None;
    bool m_loaded = false, m_more = false;
    int m_offset = 0, m_requestedOffset = 0;
};
}
