#pragma once
#include <QWidget>
#include <QJsonObject>
#include <functional>
class BackendTransport;
class QCheckBox;
class QPlainTextEdit;
class QPushButton;
class QLabel;
class QListWidget;
class QTimer;
namespace pixiu {
class PrivacyPage : public QWidget
{
    Q_OBJECT
public:
    explicit PrivacyPage(QWidget *parent, BackendTransport *transport = nullptr);
    bool hasPendingOperation() const { return m_pending != Pending::None; }
    bool hasUnsavedChanges() const;
    void notifyDataChanged();
    void setDirectoryPicker(std::function<QString(QWidget *)> picker);
protected:
    void showEvent(QShowEvent *event) override;
private:
    enum class Pending { None, Load, Save, Logs, Directory };
    void controls();
    void loadLogs(int offset);
    void scheduleRefresh();
    BackendTransport *m_transport;
    QCheckBox *m_enabled, *m_directory, *m_behavior;
    QPlainTextEdit *m_directories;
    QPushButton *m_load, *m_save, *m_logs, *m_previous, *m_next;
    QPushButton *m_browse;
    std::function<QString(QWidget *)> m_directoryPicker;
    QLabel *m_status;
    QListWidget *m_events;
    QJsonObject m_config;
    Pending m_pending = Pending::None;
    bool m_loaded = false, m_more = false;
    int m_offset = 0, m_requestedOffset = 0;
    QTimer *m_refreshTimer;
    bool m_refreshNeeded = false;
};
}
