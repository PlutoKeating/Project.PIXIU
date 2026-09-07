#pragma once
#include "AgentEvidence.h"
#include <QObject>
#include <QNetworkAccessManager>
#include <QNetworkRequest>
#include <QPointer>
#include <QTimer>

class QNetworkReply;
namespace pixiu {
class AgentEvidenceClient : public QObject {
    Q_OBJECT
public:
    explicit AgentEvidenceClient(QObject *parent = nullptr, int timeoutMs = 10000);
    ~AgentEvidenceClient() override;
    // Caller supplies the existing Runtime endpoint/authentication, never model output.
    void load(QNetworkRequest runtime, const QString &session, const QString &scope);
    void cancel();
    bool busy() const { return !m_reply.isNull(); }
signals:
    void loaded(const QString &session, const pixiu::AgentEvidenceResult &result);
    void failed(const QString &session, const QString &message);
private:
    void fail(const QString &message);
    QNetworkAccessManager m_network;
    QPointer<QNetworkReply> m_reply;
    QTimer m_timeout;
    QByteArray m_buffer;
    QString m_session;
    QString m_scope;
};
}
