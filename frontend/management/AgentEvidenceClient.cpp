#include "AgentEvidenceClient.h"
#include <QNetworkReply>
#include <QRegularExpression>

namespace pixiu {
AgentEvidenceClient::AgentEvidenceClient(QObject *parent, int timeoutMs) : QObject(parent)
{
    m_timeout.setSingleShot(true);
    m_timeout.setInterval(qMax(1, timeoutMs));
    connect(&m_timeout, &QTimer::timeout, this, [this] { fail(tr("读取会话来源超时，请重试。")); });
}
AgentEvidenceClient::~AgentEvidenceClient() { cancel(); }
void AgentEvidenceClient::cancel()
{
    m_timeout.stop();
    auto *reply = m_reply.data();
    m_reply.clear();
    m_buffer.clear();
    if (reply) {
        reply->disconnect(this);
        reply->abort();
        reply->deleteLater();
    }
}
void AgentEvidenceClient::fail(const QString &message)
{
    const auto session = m_session;
    cancel();
    emit failed(session, message);
}
void AgentEvidenceClient::load(QNetworkRequest request, const QString &session, const QString &scope)
{
    cancel();
    m_session = session;
    m_scope = scope;
    auto url = request.url();
    const QRegularExpression safeSession(QStringLiteral("\\A[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\\z"));
    const QRegularExpression safeScope(QStringLiteral("\\A(user|shared):[A-Za-z0-9._-]+\\z"));
    if (!safeSession.match(session).hasMatch() || !safeScope.match(scope).hasMatch() ||
        !url.isValid() || url.host().isEmpty() || !url.userInfo().isEmpty() ||
        (url.scheme() != "http" && url.scheme() != "https") || url.hasQuery() || url.hasFragment()) {
        fail(tr("会话来源配置无效。"));
        return;
    }
    url.setPath("/api/sessions/" + session + "/details");
    request.setUrl(url);
    request.setAttribute(QNetworkRequest::RedirectPolicyAttribute, QNetworkRequest::ManualRedirectPolicy);
    request.setRawHeader("Accept", "application/json");
    auto *reply = m_network.get(request);
    m_reply = reply;
    reply->setReadBufferSize(64*1024);
    auto consume = [this, reply] {
        if (m_reply != reply) return;
        constexpr int limit = 2*1024*1024;
        if (reply->header(QNetworkRequest::ContentLengthHeader).toLongLong() > limit) {
            fail(tr("会话来源记录过大，未加载。"));
            return;
        }
        m_buffer += reply->read(limit + 1 - m_buffer.size());
        if (m_buffer.size() > limit) fail(tr("会话来源记录过大，未加载。"));
    };
    connect(reply, &QNetworkReply::metaDataChanged, this, consume);
    connect(reply, &QNetworkReply::readyRead, this, consume);
    connect(reply, &QNetworkReply::finished, this, [this, reply, consume] {
        if (m_reply != reply) return;
        consume();
        if (m_reply != reply) return;
        const int status = reply->attribute(QNetworkRequest::HttpStatusCodeAttribute).toInt();
        if (reply->error() != QNetworkReply::NoError || status != 200) {
            fail(tr("会话来源读取失败，请检查 Runtime 连接后重试。"));
            return;
        }
        const auto result = parseAgentEvidence(m_buffer, m_session, m_scope);
        const auto session = m_session;
        m_timeout.stop();
        m_reply.clear();
        m_buffer.clear();
        reply->deleteLater();
        emit loaded(session, result);
    });
    m_timeout.start();
}
}
