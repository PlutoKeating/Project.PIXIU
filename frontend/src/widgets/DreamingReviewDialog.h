#pragma once
#include <QDialog>
#include <QJsonArray>
#include <QUrl>
class QListWidget;
class QPlainTextEdit;
class QPushButton;
class QLabel;
class QNetworkAccessManager;
namespace pixiu {
class DreamingReviewDialog final : public QDialog {
    Q_OBJECT
public:
    explicit DreamingReviewDialog(const QUrl &endpoint, QWidget *parent = nullptr);
    void refresh();
signals:
    void pendingChanged(int count);
private:
    void decide(bool approve);
    void selected();
    QUrl m_endpoint;
    QNetworkAccessManager *m_network;
    QListWidget *m_plans;
    QPlainTextEdit *m_before;
    QPlainTextEdit *m_after;
    QPushButton *m_approve;
    QPushButton *m_reject;
    QLabel *m_status;
    QJsonArray m_records;
    bool m_busy = false;
};
}
