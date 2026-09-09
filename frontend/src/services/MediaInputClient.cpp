#include "MediaInputClient.h"
#include <QFile>
#include <QFileInfo>
#include <QJsonDocument>
#include <QJsonObject>
#include <QNetworkReply>
namespace pixiu {
void MediaInputClient::prepare(const QNetworkRequest &runtime, const QStringList &paths)
{
    m_runtime = runtime; m_paths = paths; m_parts = {}; next();
}
void MediaInputClient::next()
{
    if (m_paths.isEmpty()) { emit prepared(m_parts); return; }
    const auto path = m_paths.takeFirst();
    QFile file(path);
    if (!file.open(QIODevice::ReadOnly) || file.size() > 6*1024*1024) {
        emit failed(tr("附件无法读取或过大，尚未发送。")); return;
    }
    auto request = m_runtime; auto url = request.url();
    url.setPath("/api/memory/attachment"); url.setQuery(QString()); request.setUrl(url);
    request.setAttribute(QNetworkRequest::RedirectPolicyAttribute, QNetworkRequest::ManualRedirectPolicy);
    request.setHeader(QNetworkRequest::ContentTypeHeader, "application/json"); request.setTransferTimeout(90000);
    const QJsonObject payload{{"filename", QFileInfo(path).fileName()}, {"file_base64", QString::fromLatin1(file.readAll().toBase64())}};
    auto *reply = m_network.post(request, QJsonDocument(payload).toJson(QJsonDocument::Compact));
    connect(reply, &QNetworkReply::finished, this, [this, reply, path] {
        const auto result = QJsonDocument::fromJson(reply->readAll()).object();
        const bool ok = reply->error() == QNetworkReply::NoError
            && reply->attribute(QNetworkRequest::HttpStatusCodeAttribute).toInt() == 200;
        reply->deleteLater();
        if (!ok || !result.value("content").isArray()) {
            emit failed(result.value("error").toObject().value("message").toString(tr("当前附件读取不可用，详情见设置。"))); return;
        }
        m_parts.append(QJsonObject{{"type", "text"}, {"text", tr("附件：%1").arg(QFileInfo(path).fileName())}});
        for (const auto &part : result.value("content").toArray()) m_parts.append(part);
        if (QJsonDocument(m_parts).toJson(QJsonDocument::Compact).size() > 8*1024*1024) {
            emit failed(tr("附件内容过大，尚未发送。")); return;
        }
        next();
    });
}
}
