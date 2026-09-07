#pragma once
#include <QWidget>
class BackendTransport;
namespace pixiu {
class DeliveryPage : public QWidget
{
    Q_OBJECT
public:
    explicit DeliveryPage(QWidget *parent, BackendTransport *transport = nullptr);
signals:
    void searchRequested(const QString &text);
};
}
