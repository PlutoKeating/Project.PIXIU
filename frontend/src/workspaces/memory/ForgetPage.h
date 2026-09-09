#pragma once
#include <QWidget>
#include <QJsonObject>
#include <QElapsedTimer>
#include <QStringList>
class BackendTransport;
class QComboBox;
class QLineEdit;
class QPlainTextEdit;
class QPushButton;
class QLabel;
class QTimer;
namespace pixiu {
class ForgetPage : public QWidget
{
    Q_OBJECT
public:
    explicit ForgetPage(QWidget *parent, BackendTransport *transport = nullptr);
    bool setAgentIntent(const QString &command, const QString &scope);
    bool hasPendingOperation() const { return m_pending != Pending::None; }
signals:
    void memoryForgotten();
private:
    enum class Pending { None, Preview, Confirm };
    void controls();
    void invalidate();
    BackendTransport *m_transport;
    QLineEdit *m_command;
    QComboBox *m_scope;
    QPlainTextEdit *m_targets;
    QPushButton *m_preview, *m_confirm, *m_cancel;
    QLabel *m_status;
    QTimer *m_expiry;
    QElapsedTimer m_clock;
    QJsonObject m_payload;
    QString m_token;
    QStringList m_targetIds;
    Pending m_pending = Pending::None;
};
}
