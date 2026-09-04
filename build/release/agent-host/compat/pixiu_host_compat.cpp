#include "services/apiservice.h"
#include "ui/mainwindow.h"
#include "ui/settingsdialog.h"

#include <QApplication>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QNetworkRequest>
#include <QSettings>
#include <QUrl>

namespace {

QUrl runtimeUrl(const QString &configured, const QString &path)
{
    QString endpoint = configured.trimmed();
    if (!endpoint.contains(QStringLiteral("://"))) {
        endpoint.prepend(QStringLiteral("http://"));
    }
    QUrl url(endpoint);
    if (url.host() == QStringLiteral("0.0.0.0")) {
        url.setHost(QStringLiteral("127.0.0.1"));
    }
    if (url.port() < 0) {
        url.setPort(8642);
    }
    url.setPath(path);
    return url;
}

QString streamText(const QByteArray &payload)
{
    const QJsonDocument document = QJsonDocument::fromJson(payload);
    if (!document.isObject()) {
        return QString();
    }
    const QJsonObject object = document.object();
    const QJsonArray choices = object.value(QStringLiteral("choices")).toArray();
    if (!choices.isEmpty()) {
        const QJsonObject choice = choices.first().toObject();
        const QString delta = choice.value(QStringLiteral("delta"))
                                  .toObject().value(QStringLiteral("content")).toString();
        if (!delta.isEmpty()) {
            return delta;
        }
        const QString message = choice.value(QStringLiteral("message"))
                                    .toObject().value(QStringLiteral("content")).toString();
        if (!message.isEmpty()) {
            return message;
        }
    }
    return object.value(QStringLiteral("content")).toString();
}

void applyAuthentication(QNetworkRequest *request)
{
    const QString key = QSettings().value(QStringLiteral("General/BackendApiKey"))
                            .toString().trimmed();
    if (!key.isEmpty()) {
        request->setRawHeader("Authorization", QStringLiteral("Bearer %1").arg(key).toUtf8());
    }
}

} // namespace

void ApiService::sendChatCompletion(const QString &sessionId,
                                    const QJsonArray &messages,
                                    const QString &model)
{
    cancelChatCompletion(sessionId);

    QJsonObject body{
        {QStringLiteral("messages"), messages},
        {QStringLiteral("model"), model.isEmpty() ? QStringLiteral("default") : model},
        {QStringLiteral("stream"), true},
    };
    QNetworkRequest request(runtimeUrl(m_apiUrl, QStringLiteral("/v1/chat/completions")));
    request.setHeader(QNetworkRequest::ContentTypeHeader, QStringLiteral("application/json"));
    applyAuthentication(&request);
    if (!sessionId.trimmed().isEmpty()) {
        request.setRawHeader("X-Hermes-Session-Id", sessionId.trimmed().toUtf8());
    }

    QNetworkReply *reply = m_networkManager->post(request, QJsonDocument(body).toJson());
    StreamState state;
    state.reply = reply;
    m_streams.insert(sessionId, state);
    reply->setProperty("pixiu-stream-text", QString());

    auto consume = [this, reply, sessionId]() {
        auto it = m_streams.find(sessionId);
        if (it == m_streams.end() || it->reply != reply) {
            return;
        }
        it->partialData.append(QString::fromUtf8(reply->readAll()));
        int newline = it->partialData.indexOf(QLatin1Char('\n'));
        while (newline >= 0) {
            QString line = it->partialData.left(newline).trimmed();
            it->partialData.remove(0, newline + 1);
            if (line.startsWith(QStringLiteral("data:"))) {
                line = line.mid(5).trimmed();
            }
            if (!line.isEmpty() && line != QStringLiteral("[DONE]")) {
                const QString delta = streamText(line.toUtf8());
                if (!delta.isEmpty()) {
                    reply->setProperty("pixiu-stream-text",
                                       reply->property("pixiu-stream-text").toString() + delta);
                    it->receivedContent = true;
                    emit chatCompletionDelta(sessionId, delta);
                }
            }
            newline = it->partialData.indexOf(QLatin1Char('\n'));
        }
    };

    connect(reply, &QNetworkReply::readyRead, this, consume);
    connect(reply, &QNetworkReply::finished, this, [this, reply, sessionId, consume]() {
        auto it = m_streams.find(sessionId);
        if (it == m_streams.end() || it->reply != reply) {
            reply->deleteLater();
            return;
        }
        consume();
        if (!it->partialData.trimmed().isEmpty()) {
            it->partialData.append(QLatin1Char('\n'));
            consume();
        }
        const bool ok = reply->error() == QNetworkReply::NoError;
        QString content = reply->property("pixiu-stream-text").toString().trimmed();
        if (ok && content.isEmpty()) {
            content = streamText(it->partialData.toUtf8()).trimmed();
        }
        const QString failure = reply->errorString();
        m_streams.erase(it);
        if (!ok) {
            emit error(failure);
        }
        emit chatCompletionFinished(sessionId, content, ok);
        reply->deleteLater();
    });
}

void ApiService::cancelChatCompletion(const QString &sessionId)
{
    cancelStreamForSession(sessionId, true);
}

void ApiService::cancelStreamForSession(const QString &sessionId, bool emitCompletion)
{
    auto it = m_streams.find(sessionId);
    if (it == m_streams.end()) {
        return;
    }
    QNetworkReply *reply = it->reply;
    m_streams.erase(it);
    if (reply && reply->isRunning()) {
        reply->abort();
    }
    if (emitCompletion) {
        emit chatCompletionFinished(sessionId, QString(), false);
    }
}

void MainWindow::showFromTray()
{
    showNormal();
    raise();
    activateWindow();
}

void MainWindow::toggleFromTaskbar()
{
    if (isVisible() && !isMinimized() && isActiveWindow()) {
        hide();
        return;
    }
    showFromTray();
}

void SettingsTitleBar::mousePressEvent(QMouseEvent *event)
{
    if (event->button() == Qt::LeftButton) {
        emit dragPressed(event->globalPos());
    }
    QWidget::mousePressEvent(event);
}

void SettingsTitleBar::mouseMoveEvent(QMouseEvent *event)
{
    if (event->buttons().testFlag(Qt::LeftButton)) {
        emit dragMoved(event->globalPos());
    }
    QWidget::mouseMoveEvent(event);
}

void SettingsTitleBar::mouseReleaseEvent(QMouseEvent *event)
{
    if (event->button() == Qt::LeftButton) {
        emit dragReleased();
    }
    QWidget::mouseReleaseEvent(event);
}
