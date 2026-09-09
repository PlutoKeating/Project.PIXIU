#pragma once
#include <QDialog>
#include <QJsonObject>
#include <QNetworkRequest>
class BackendTransport;
class QLineEdit;
class QPlainTextEdit;
class QComboBox;
class QTableWidget;
class QLabel;
class QPushButton;
namespace pixiu {
class MemoryWriteDialog : public QDialog
{
    Q_OBJECT
public:
    explicit MemoryWriteDialog(QWidget *parent, BackendTransport *transport = nullptr);
    void reject() override;
    void setRuntimeRequest(const QNetworkRequest &request) { m_runtimeRequest = request; }
signals:
    void memoryAccepted(const QString &evidenceId);
private:
    void submit();
    void updateForm();
    BackendTransport *m_transport;
    QLineEdit *m_title;
    QPlainTextEdit *m_body;
    QComboBox *m_scope;
    QLabel *m_status;
    QPushButton *m_save;
    QPushButton *m_cancel;
    QNetworkRequest m_runtimeRequest;
    QTableWidget *m_items;
    QPushButton *m_image;
    QJsonObject m_originalImage;
    bool m_ocrBusy = false;
    bool m_busy = false;
    QJsonObject m_lastPayload;
    QString m_idempotencyKey;
};
}
