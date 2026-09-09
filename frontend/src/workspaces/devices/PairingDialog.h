#pragma once
#include <QDialog>
#include <QElapsedTimer>
class BackendTransport;
class QComboBox;
class QLabel;
class QLineEdit;
class QPlainTextEdit;
class QPushButton;
class QTimer;
namespace pixiu {
class PairingDialog : public QDialog
{
    Q_OBJECT
public:
    explicit PairingDialog(QWidget *parent, BackendTransport *transport = nullptr);
    void reject() override;
signals:
    void localTrustEstablished();
private:
    enum class Pending { None, Token, Pair };
    void controls();
    void clearLocalToken();
    bool showQrToken(const QString &token);
    BackendTransport *m_transport;
    QComboBox *m_method;
    QLineEdit *m_localPin, *m_remotePin;
    QPlainTextEdit *m_localToken, *m_remoteToken;
    QPushButton *m_generate, *m_pair, *m_close;
    QLabel *m_status, *m_tokenStatus, *m_qr;
    QTimer *m_expiry;
    QElapsedTimer m_generationClock;
    Pending m_pending = Pending::None;
    QString m_requestedMethod;
};
}
