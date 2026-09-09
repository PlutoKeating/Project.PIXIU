#pragma once
#include <QString>
#include <QWidget>
class BackendTransport;
class QListWidget;
class QPlainTextEdit;
class QLabel;
class QTimer;
namespace pixiu {
class DeliveryPage : public QWidget
{
    Q_OBJECT
public:
    explicit DeliveryPage(QWidget *parent, BackendTransport *transport = nullptr);
    bool hasPendingOperation() const { return m_pending != None; }
    void notifyDataChanged();
protected:
    void showEvent(QShowEvent *event) override;
signals:
    void searchRequested(const QString &text);
private:
    void scheduleRefresh();
    QTimer *m_refreshTimer;
    bool m_refreshNeeded = true;
    bool m_autoDigest = false;
    enum Pending { None, Insights, Digest };
    Pending m_pending = None;
    QString m_digestDate;
    QListWidget *m_items;
    QPlainTextEdit *m_body;
    QLabel *m_status;
    bool m_invalidated = false;
};
}
