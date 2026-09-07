#pragma once
#include <QString>
#include <QWidget>
class BackendTransport;
namespace pixiu {
class DeliveryPage : public QWidget
{
    Q_OBJECT
public:
    explicit DeliveryPage(QWidget *parent, BackendTransport *transport = nullptr);
    bool hasPendingOperation() const { return m_pending != None; }
signals:
    void searchRequested(const QString &text);
private:
    enum Pending { None, Insights, Digest };
    Pending m_pending = None;
    QString m_digestDate;
};
}
