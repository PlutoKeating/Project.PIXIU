#pragma once
#include <QObject>
class QWidget;

namespace pixiu {
// One guard belongs to the Agent host; embedded pages do not own application exit.
class HostCloseGuard : public QObject
{
    Q_OBJECT
public:
    explicit HostCloseGuard(QWidget *host);
protected:
    bool eventFilter(QObject *watched, QEvent *event) override;
private:
    QWidget *m_host;
    bool m_checking = false;
};
}
