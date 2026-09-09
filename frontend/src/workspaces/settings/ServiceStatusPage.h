#pragma once
#include <QWidget>
class BackendTransport;
namespace pixiu {
class ServiceStatusPage : public QWidget
{
    Q_OBJECT
public:
    explicit ServiceStatusPage(QWidget *parent, BackendTransport *transport = nullptr);
    bool hasPendingOperation() const { return m_pending; }
private:
    bool m_pending = false;
};
}
