#pragma once
#include <QSet>
#include <QWidget>

class QLabel;
class QPushButton;

namespace pixiu {
// Notifications only: never treats a broadcast as authority to perform a write.
class BackendEventStatus : public QWidget
{
    Q_OBJECT
public:
    explicit BackendEventStatus(const QString &baseUrl, QWidget *parent = nullptr);
private:
    void updateNotice();
    QLabel *m_notice;
    QPushButton *m_dismiss;
    QSet<QString> m_changed;
};
}
