#include "services/WebSocketClient.h"

#include <QJsonDocument>
#include <QLoggingCategory>
#include <QSet>
#include <QUrl>
#include <QWebSocket>

Q_LOGGING_CATEGORY(lcWs, "pixiu.websocket")

namespace {
constexpr int kMaxReconnectDelayMs = 30000;
constexpr int kInitialReconnectDelayMs = 1000;

// API 契约已定义的业务事件（docs/API.md §4）。
// 未列入的未知事件仅记录并忽略，保持前向兼容：不崩溃、不断开、不向上分发。
bool isKnownBusinessEvent(const QString &name)
{
    static const QSet<QString> kKnownEvents = {
        QStringLiteral("memory_ready"),
        QStringLiteral("conflict_detected"),
        QStringLiteral("forget_confirmation"),
        QStringLiteral("sync_event"),
    };
    return kKnownEvents.contains(name);
}
}

WebSocketClient::WebSocketClient(QObject *parent)
    : QObject(parent)
    , m_socket(new QWebSocket(QString(), QWebSocketProtocol::VersionLatest, this))
{
    m_reconnectTimer.setSingleShot(true);

    connect(m_socket, &QWebSocket::connected, this, [this]() {
        qCInfo(lcWs) << "connected to" << m_wsUrl;
        m_reconnectAttempts = 0;
        m_reconnectTimer.stop();
        emit connectionStateChanged(ConnectionState::Connected);
    });
    connect(m_socket, &QWebSocket::disconnected, this, [this]() {
        qCInfo(lcWs) << "disconnected from" << m_wsUrl;
        emit connectionStateChanged(ConnectionState::Disconnected);
        if (!m_stopped) {
            scheduleReconnect();
        }
    });
    connect(m_socket, &QWebSocket::textMessageReceived, this,
            &WebSocketClient::onTextMessageReceived);
    connect(m_socket, QOverload<QAbstractSocket::SocketError>::of(&QWebSocket::error),
            this, [this](QAbstractSocket::SocketError error) {
                qCWarning(lcWs) << "socket error:" << int(error) << m_socket->errorString();
                emit connectionStateChanged(ConnectionState::Error);
                if (!m_stopped) {
                    scheduleReconnect();
                }
            });

    connect(&m_reconnectTimer, &QTimer::timeout, this, [this]() {
        if (m_stopped || m_socket->state() == QAbstractSocket::ConnectedState) {
            return;
        }
        qCInfo(lcWs) << "reconnecting (attempt" << m_reconnectAttempts + 1 << ")";
        emit connectionStateChanged(ConnectionState::Connecting);
        m_socket->open(QUrl(m_wsUrl));
    });
}

WebSocketClient::~WebSocketClient() = default;

void WebSocketClient::setBackendUrl(const QString &baseUrl)
{
    QString url = baseUrl;
    if (url.startsWith(QStringLiteral("https://"))) {
        url.replace(0, 8, QStringLiteral("wss://"));
    } else if (url.startsWith(QStringLiteral("http://"))) {
        url.replace(0, 7, QStringLiteral("ws://"));
    }
    if (!url.endsWith(QLatin1Char('/'))) {
        url += QLatin1Char('/');
    }
    m_wsUrl = url + QStringLiteral("events");
}

void WebSocketClient::connectToBackend()
{
    if (m_wsUrl.isEmpty()) {
        qCWarning(lcWs) << "no backend URL configured";
        return;
    }
    m_stopped = false;
    m_reconnectAttempts = 0;
    m_reconnectTimer.stop();
    emit connectionStateChanged(ConnectionState::Connecting);
    m_socket->open(QUrl(m_wsUrl));
}

void WebSocketClient::disconnectFromBackend()
{
    m_stopped = true;
    m_reconnectTimer.stop();
    m_socket->close();
    emit connectionStateChanged(ConnectionState::Disconnected);
}

bool WebSocketClient::isConnected() const
{
    return m_socket->state() == QAbstractSocket::ConnectedState;
}

void WebSocketClient::scheduleReconnect()
{
    if (m_stopped || m_reconnectTimer.isActive()) {
        return;
    }
    const int delayMs = qMin(kMaxReconnectDelayMs,
                             kInitialReconnectDelayMs * (1 << qMin(m_reconnectAttempts, 5)));
    ++m_reconnectAttempts;
    qCInfo(lcWs) << "scheduling reconnect in" << delayMs << "ms";
    m_reconnectTimer.start(delayMs);
}

void WebSocketClient::resetReconnect()
{
    m_reconnectAttempts = 0;
    m_reconnectTimer.stop();
}

void WebSocketClient::onTextMessageReceived(const QString &message)
{
    QJsonParseError parseError;
    const QJsonDocument doc = QJsonDocument::fromJson(message.toUtf8(), &parseError);
    if (parseError.error != QJsonParseError::NoError || !doc.isObject()) {
        qCWarning(lcWs) << "ignoring malformed event frame:" << parseError.errorString();
        return;
    }

    const QJsonObject event = doc.object();
    const QString name = event.value(QStringLiteral("event")).toString();
    if (name.isEmpty()) {
        qCWarning(lcWs) << "ignoring event frame without 'event' field";
        return;
    }

    // 控制事件只维护连接状态，不进入业务分发。
    if (name == QStringLiteral("connected") || name == QStringLiteral("ping")) {
        qCInfo(lcWs) << "control event:" << name;
        return;
    }

    if (!isKnownBusinessEvent(name)) {
        // 未知事件：只记录事件名，不崩溃、不断开、不向上分发。
        qCInfo(lcWs) << "ignoring unknown event:" << name;
        return;
    }

    const QJsonValue data = event.value(QStringLiteral("data"));
    if (!data.isObject()) {
        // 脱敏诊断：仅记录事件名与 data 状态，不输出原始 payload。
        const QString dataState =
            data.isUndefined() ? QStringLiteral("missing") : QStringLiteral("non-object");
        qCWarning(lcWs) << "ignoring event" << name << "with" << dataState << "data";
        return;
    }

    qCInfo(lcWs) << "business event:" << name;
    emit eventReceived(event);
}
