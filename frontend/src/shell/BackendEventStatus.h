#pragma once
#include <QSet>
#include <QWidget>
#include <QElapsedTimer>

class QLabel;
class QPushButton;

namespace pixiu {
// Notifications only: never treats a broadcast as authority to perform a write.
class BackendEventStatus : public QWidget
{
    Q_OBJECT
public:
    explicit BackendEventStatus(const QString &baseUrl, QWidget *parent = nullptr);
signals:
    // Allowlisted event name, or "reconnected"; carries no command or credential.
    void dataChanged(const QString &eventName);
    void conflictAttentionRequested();
private:
    void updateNotice();
    QLabel *m_notice;
    QLabel *m_progress;
    QPushButton *m_dismiss;
    QSet<QString> m_changed;
    QElapsedTimer m_lastAttention;
};
}
