#include "services/HttpBackendTransport.h"

#include <QJsonArray>
#include <QJsonDocument>
#include <QLoggingCategory>
#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QNetworkRequest>
#include <QTimer>
#include <QUrl>
#include <QUrlQuery>

Q_LOGGING_CATEGORY(lcHttp, "pixiu.http")

namespace {
constexpr int kTransferTimeoutMs = 10000;
}

HttpBackendTransport::HttpBackendTransport(QObject *parent, int healthProbeIntervalMs)
    : BackendTransport(parent)
    , m_network(new QNetworkAccessManager(this))
    , m_healthTimer(new QTimer(this))
    , m_baseUrl(qEnvironmentVariable(
        "PIXIU_BACKEND_URL", QStringLiteral("http://127.0.0.1:8765")))
{
    if (m_baseUrl.endsWith(QLatin1Char('/'))) {
        m_baseUrl.chop(1);
    }
    // 周期健康探测：后端未连接时静默跳过；Disconnected 状态由
    // disconnectFromBackend() 停止，connectToBackend() 恢复。
    m_healthTimer->setInterval(healthProbeIntervalMs);
    connect(m_healthTimer, &QTimer::timeout, this, &HttpBackendTransport::probeHealth);
}

void HttpBackendTransport::connectToBackend()
{
    if (m_state == ConnectionState::Connecting || m_state == ConnectionState::Connected) {
        return;
    }
    setConnectionState(ConnectionState::Connecting);
    if (!m_healthTimer->isActive()) {
        m_healthTimer->start();
    }
    probeHealth();
}

void HttpBackendTransport::disconnectFromBackend()
{
    m_healthTimer->stop();
    setConnectionState(ConnectionState::Disconnected);
}

void HttpBackendTransport::probeHealth()
{
    // 显式断开后不探测；上一轮探测未返回（后端黑洞/慢响应）时不叠加请求。
    if (m_state == ConnectionState::Disconnected || m_healthInFlight) {
        return;
    }
    m_healthInFlight = true;
    QNetworkRequest request(endpoint(QStringLiteral("/conflicts")));
    request.setTransferTimeout(kTransferTimeoutMs);
    QNetworkReply *reply = m_network->get(request);
    connect(reply, &QNetworkReply::finished, this, [this, reply]() {
        reply->deleteLater();
        m_healthInFlight = false;
        // HTTP 4xx/5xx 也说明后端可达（服务在跑），仅传输层失败才算离线。
        if (reply->error() == QNetworkReply::NoError) {
            setConnectionState(ConnectionState::Connected);
        } else {
            setConnectionState(ConnectionState::Error);
        }
    });
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

void HttpBackendTransport::extractPreferences(const QJsonObject &payload)
{
    postJson(QStringLiteral("/preference/extract"), payload,
             [this](quint64, const QJsonObject &obj) {
                 emit preferenceExtractResult(obj);
             });
}

void HttpBackendTransport::preferencesList(const QString &scope)
{
    QString path = QStringLiteral("/preferences");
    if (!scope.isEmpty()) {
        path += QStringLiteral("?scope=") + QUrl::toPercentEncoding(scope);
    }
    getJson(path,
            [this](quint64, const QJsonObject &obj) {
                emit preferencesListResult(
                    obj.value(QStringLiteral("preferences")).toArray());
            });
}

void HttpBackendTransport::evidenceDetail(const QString &evidenceId)
{
    getJson(QStringLiteral("/evidence/") + evidenceId,
            [this](quint64, const QJsonObject &obj) { emit evidenceDetailResult(obj); });
}

void HttpBackendTransport::createPairingToken(const QJsonObject &payload)
{
    postJson(QStringLiteral("/sync/token"), payload,
             [this](quint64, const QJsonObject &obj) {
                 emit pairingTokenResult(obj);
             });
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

void HttpBackendTransport::discoverDevices()
{
    // 与 listPeers 一致携带完整响应体，供上层区分契约成功态与退化态。
    getJson(QStringLiteral("/sync/discover"),
            [this](quint64, const QJsonObject &obj) { emit devicesLoaded(obj); });
}

void HttpBackendTransport::requestPairing(const QString &targetId)
{
    QJsonObject body;
    body.insert(QStringLiteral("target_device_id"), targetId);
    postJson(QStringLiteral("/sync/pair/request"), body,
             [this](quint64, const QJsonObject &obj) {
                 emit pairRequestResult(obj);
             });
}

void HttpBackendTransport::confirmPairing(const QString &requestId, bool accept)
{
    QJsonObject body;
    body.insert(QStringLiteral("request_id"), requestId);
    body.insert(QStringLiteral("accept"), accept);
    postJson(QStringLiteral("/sync/pair/confirm"), body,
             [this](quint64, const QJsonObject &obj) {
                 emit pairConfirmResult(obj);
             });
}

void HttpBackendTransport::updateSyncSettings(bool enabled, bool paused)
{
    QJsonObject body;
    body.insert(QStringLiteral("enabled"), enabled);
    body.insert(QStringLiteral("paused"), paused);
    putJson(QStringLiteral("/sync/settings"), body,
            [this](quint64, const QJsonObject &obj) {
                emit settingsResult(obj);
            });
}

void HttpBackendTransport::monitorConfig()
{
    getJson(QStringLiteral("/monitor/config"),
            [this](quint64, const QJsonObject &obj) { emit configResult(obj); });
}

void HttpBackendTransport::updateMonitorConfig(const QJsonObject &payload)
{
    putJson(QStringLiteral("/monitor/config"), payload,
            [this](quint64, const QJsonObject &obj) { emit configResult(obj); });
}

void HttpBackendTransport::monitorLog(int limit, int offset)
{
    // QUrlQuery 负责参数编码；响应只取契约字段 events，多余字段忽略。
    QUrlQuery query;
    query.addQueryItem(QStringLiteral("limit"), QString::number(limit));
    query.addQueryItem(QStringLiteral("offset"), QString::number(offset));
    QString path = QStringLiteral("/monitor/log");
    const QString encoded = query.toString(QUrl::FullyEncoded);
    if (!encoded.isEmpty()) {
        path += QLatin1Char('?') + encoded;
    }
    getJson(path,
            [this](quint64, const QJsonObject &obj) {
                emit monitorLogResult(
                    obj.value(QStringLiteral("events")).toArray());
            });
}

void HttpBackendTransport::deliveryInsights()
{
    // B4-1：最近 24h 高质量记忆候选（limit 固定 3，欢迎页动态建议卡）。
    // 空数组是空库/runtime 未启动的合法退化态，透传给上层保留静态兜底。
    QString path = QStringLiteral("/delivery/insights?limit=3");
    getJson(path,
            [this](quint64, const QJsonObject &obj) {
                emit insightsResult(
                    obj.value(QStringLiteral("insights")).toArray());
            });
}

void HttpBackendTransport::deliveryDigest()
{
    // B4-2：今日简报（缺省日期 = 今天，本地时区日边界由服务端处理）。
    getJson(QStringLiteral("/delivery/digest"),
            [this](quint64, const QJsonObject &obj) {
                emit digestResult(obj);
            });
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
                      QStringLiteral("PIXIU-Frontend/") + QStringLiteral(PIXIU_VERSION));
    request.setTransferTimeout(kTransferTimeoutMs);
    const QByteArray payload = QJsonDocument(body).toJson(QJsonDocument::Compact);
    QNetworkReply *reply = m_network->post(request, payload);
    handleReply(reply, onSuccess, QStringLiteral("NETWORK_ERROR"), tag);
}

void HttpBackendTransport::putJson(const QString &path,
                                   const QJsonObject &body,
                                   const std::function<void(quint64, const QJsonObject &)> &onSuccess,
                                   quint64 tag)
{
    QNetworkRequest request(endpoint(path));
    request.setHeader(QNetworkRequest::ContentTypeHeader, QStringLiteral("application/json"));
    request.setHeader(QNetworkRequest::KnownHeaders::UserAgentHeader,
                      QStringLiteral("PIXIU-Frontend/") + QStringLiteral(PIXIU_VERSION));
    request.setTransferTimeout(kTransferTimeoutMs);
    const QByteArray payload = QJsonDocument(body).toJson(QJsonDocument::Compact);
    QNetworkReply *reply = m_network->put(request, payload);
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
