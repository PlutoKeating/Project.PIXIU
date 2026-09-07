#pragma once
#include <QObject>

class QWidget;
namespace pixiu {
// An optional entry to the existing host, never a second application/window.
class HostTray : public QObject
{
    Q_OBJECT
public:
    explicit HostTray(QWidget *host);
};
}
