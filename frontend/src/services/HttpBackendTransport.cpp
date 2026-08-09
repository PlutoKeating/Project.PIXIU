#include "services/HttpBackendTransport.h"

#include <QJsonArray>
#include <QJsonDocument>
#include <QLoggingCategory>
#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QNetworkRequest>
#include <QUrl>

Q_LOGGING_CATEGORY(lcHttp, "pixiu.http")

namespace {
constexpr int kTransferTimeoutMs = 10000;
}

HttpBackendTransport::HttpBackendTransport(QObject *parent)
    : BackendTransport(parent)
    , m_network(new QNetworkAccessManager(this))
    , m_baseUrl(qEnvironmentVariable(
        "PIXIU_BACKEND_URL", QStringLiteral("http://127.0.0.1:8765")))
{
    if (m_baseUrl.endsWith(QLatin1Char('/'))) {
        m_baseUrl.chop(1);
    }
}

void HttpBackendTransport::connectToBackend()
{
    if (m_state == ConnectionState::Connecting || m_state == ConnectionState::Connected) {
        return;
    }
    setConnectionState(ConnectionState::Connecting);
    // 健康探测：GET /conflicts（已实现端点，开销小）。
    listConflicts();
}

void HttpBackendTransport::disconnectFromBackend()
{
    setConnectionState(ConnectionState::Disconnected);
}

quint64 HttpBackendTransport::queryMemory(const QString &text, const QJsonObject &contextHint)
{
    const quint64 requestId = m_nextRequestId++;
    QJsonObject body;
    body.insert(QStringLiteral("text"), text);
    if (!contextHint.isEmpty()) {
        body.insert(QStringLiteral("context_hint"), contextHint);
    }
    postJson(QStringLiteral("/memory/query"), body,
             [this, requestId](quint64, const QJsonObject &obj) {
                 emit queryResult(requestId, obj);
             },
             requestId);
    return requestId;
}

void HttpBackendTransport::writeMemory(const QJsonObject &payload)
{
    postJson(QStringLiteral("/memory/write"), payload,
             [this](quint64, const QJsonObject &obj) { emit writeAcknowledged(obj); });
}

void HttpBackendTransport::forget(const QString &command, bool confirm)
{
    QJsonObject body;
    body.insert(QStringLiteral("command"), command);
    body.insert(QStringLiteral("confirm"), confirm);
    postJson(QStringLiteral("/forget"), body,
             [this](quint64, const QJsonObject &obj) { emit forgetResult(obj); });
}

void HttpBackendTransport::listConflicts()
{
    getJson(QStringLiteral("/conflicts"),
            [this](quint64, const QJsonObject &obj) {
                emit conflictsResult(
                    obj.value(QStringLiteral("conflicts")).toArray());
            });
}

void HttpBackendTransport::preferenceHistory(const QString &preferenceId)
{
    getJson(QStringLiteral("/preference/") + preferenceId + QStringLiteral("/history"),
            [this](quint64, const QJsonObject &obj) { emit preferenceHistoryResult(obj); });
}

void HttpBackendTransport::promoteMemory(const QJsonObject &payload)
{
    postJson(QStringLiteral("/memory/flow/promote"), payload,
             [this](quint64, const QJsonObject &obj) { emit promoteResult(obj); });
}

void HttpBackendTransport::pairDevice(const QJsonObject &payload)
{
    postJson(QStringLiteral("/sync/pair"), payload,
             [this](quint64, const QJsonObject &obj) { emit pairResult(obj); });
}

void HttpBackendTransport::listPeers()
{
    getJson(QStringLiteral("/sync/peers"),
            [this](quint64, const QJsonObject &obj) { emit peersResult(obj); });
}

void HttpBackendTransport::syncStatus()
{
    getJson(QStringLiteral("/sync/status"),
            [this](quint64, const QJsonObject &obj) { emit syncStatusResult(obj); });
}

void HttpBackendTransport::revokePeer(const QString &peerId)
{
    postJson(QStringLiteral("/sync/peers/") + peerId + QStringLiteral("/revoke"),
             QJsonObject(),
             [this](quint64, const QJsonObject &obj) { emit revokeResult(obj); });
}

ConnectionState HttpBackendTransport::connectionState() const
{
    return m_state;
}

QString HttpBackendTransport::baseUrl() const
{
    return m_baseUrl;
}

QUrl HttpBackendTransport::endpoint(const QString &path) const
{
    return QUrl(m_baseUrl + path);
}

void HttpBackendTransport::getJson(const QString &path,
                                   const std::function<void(quint64, const QJsonObject &)> &onSuccess,
                                   quint64 tag)
{
    QNetworkRequest request(endpoint(path));
    request.setHeader(QNetworkRequest::ContentTypeHeader, QStringLiteral("application/json"));
    request.setTransferTimeout(kTransferTimeoutMs);
    QNetworkReply *reply = m_network->get(request);
    handleReply(reply, onSuccess, QStringLiteral("NETWORK_ERROR"), tag);
}

void HttpBackendTransport::postJson(const QString &path,
                                    const QJsonObject &body,
                                    const std::function<void(quint64, const QJsonObject &)> &onSuccess,
                                    quint64 tag)
{
    QNetworkRequest request(endpoint(path));
    request.setHeader(QNetworkRequest::ContentTypeHeader, QStringLiteral("application/json"));
    request.setHeader(QNetworkRequest::KnownHeaders::UserAgentHeader,
                      QStringLiteral("PIXIU-Frontend/0.1.0"));
    request.setTransferTimeout(kTransferTimeoutMs);
    const QByteArray payload = QJsonDocument(body).toJson(QJsonDocument::Compact);
    QNetworkReply *reply = m_network->post(request, payload);
    handleReply(reply, onSuccess, QStringLiteral("NETWORK_ERROR"), tag);
}

void HttpBackendTransport::handleReply(
    QNetworkReply *reply,
    const std::function<void(quint64, const QJsonObject &)> &onSuccess,
    const QString &fallbackErrorCode,
    quint64 tag)
{
    connect(reply, &QNetworkReply::finished, this, [this, reply, onSuccess, fallbackErrorCode, tag]() {
        reply->deleteLater();

        const QByteArray raw = reply->readAll();
        const int status = reply->attribute(QNetworkRequest::HttpStatusCodeAttribute).toInt();

        // 1) HTTP 错误（4xx/5xx）：后端可达，按 API 错误码上报。
        if (status >= 400) {
            const QJsonObject obj = QJsonDocument::fromJson(raw).object();
            const BackendError error = parseBackendError(obj);
            qCWarning(lcHttp) << "backend error:" << status
                              << error.code << error.message;
            setConnectionState(ConnectionState::Connected); // HTTP 层可达
            if (tag != 0) {
                emit queryFailed(tag,
                                 error.code.isEmpty() ? QStringLiteral("HTTP_%1").arg(status)
                                                      : error.code,
                                 error.message);
            } else {
                emit errorOccurred(error.code.isEmpty() ? QStringLiteral("HTTP_%1").arg(status)
                                                        : error.code,
                                   error.message,
                                   error.requestId);
            }
            return;
        }

        // 2) 传输层错误（网络中断/超时）。
        if (reply->error() != QNetworkReply::NoError) {
            const bool isTimeout =
                reply->error() == QNetworkReply::OperationCanceledError
                && status == 0;
            const QString code = isTimeout ? QStringLiteral("TIMEOUT") : fallbackErrorCode;
            qCWarning(lcHttp) << "request failed:" << code << reply->errorString();
            setConnectionState(ConnectionState::Error);
            if (tag != 0) {
                emit queryFailed(tag, code, reply->errorString());
            } else {
                emit errorOccurred(code, reply->errorString(), QString());
            }
            return;
        }

        // 3) 正常响应：校验 JSON 并回调。
        QJsonParseError parseError;
        const QJsonDocument doc = QJsonDocument::fromJson(raw, &parseError);
        if (parseError.error != QJsonParseError::NoError || !doc.isObject()) {
            qCWarning(lcHttp) << "invalid JSON from backend:" << parseError.errorString();
            setConnectionState(ConnectionState::Error);
            if (tag != 0) {
                emit queryFailed(tag, QStringLiteral("INVALID_RESPONSE"),
                                 tr("后端响应不是合法 JSON"));
            } else {
                emit errorOccurred(QStringLiteral("INVALID_RESPONSE"),
                                   tr("后端响应不是合法 JSON"),
                                   QString());
            }
            return;
        }

        setConnectionState(ConnectionState::Connected);
        onSuccess(tag, doc.object());
    });
}

void HttpBackendTransport::setConnectionState(ConnectionState state)
{
    if (m_state == state) {
        return;
    }
    m_state = state;
    qCInfo(lcHttp) << "connection state:" << connectionStateName(state);
    emit connectionStateChanged(state);
}
