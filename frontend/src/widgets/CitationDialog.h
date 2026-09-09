#pragma once
#include <QDialog>
#include <QVBoxLayout>
#include <QLabel>
#include <QPlainTextEdit>
#include <QScrollArea>
#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonArray>
#include <QRegularExpression>
#include <QTimer>
#include <QPixmap>
#include <QMap>

namespace pixiu {
inline QString citationText(const QJsonValue &value)
{
    if (value.isString()) return value.toString();
    if (value.isDouble()) return QString::number(value.toDouble(), 'g', 15);
    if (value.isBool()) return value.toBool() ? QObject::tr("是") : QObject::tr("否");
    QStringList lines;
    if (value.isArray()) {
        for (const auto &entry : value.toArray()) lines.append(citationText(entry));
    } else if (value.isObject()) {
        const auto fields = value.toObject();
        const QMap<QString, QString> labels{{"vendor", QObject::tr("项目")}, {"amount", QObject::tr("金额")},
            {"date", QObject::tr("日期")}, {"category", QObject::tr("类别")}, {"title", QObject::tr("标题")}};
        for (auto it = fields.begin(); it != fields.end(); ++it) {
            if (it.key() == "document_sources" || it.key() == "merged_from" || it.key() == "original_image") continue;
            const auto text = citationText(it.value());
            if (!text.isEmpty()) lines.append(labels.contains(it.key()) ? labels.value(it.key()) + "：" + text : text);
        }
    }
    return lines.join("\n");
}

// The URL supplies only trace/knowledge IDs. The backend checks the actual
// consumed reference and current permissions before returning any evidence.
inline bool openCitation(const QUrl &link, QWidget *parent)
{
    if (link.scheme() != "pixiu" || link.host() != "citation") return false;
    static const QRegularExpression path("^/ctx_[A-Za-z0-9]{26}/knw_[A-Za-z0-9_-]{8,128}$");
    if (!path.match(link.path()).hasMatch() || link.hasQuery() || link.hasFragment() || !link.userInfo().isEmpty()) return true;
    auto *dialog = new QDialog(parent);
    dialog->setAttribute(Qt::WA_DeleteOnClose);
    dialog->setWindowTitle(QObject::tr("回答来源")); dialog->resize(760, 600);
    auto *layout = new QVBoxLayout(dialog);
    auto *status = new QLabel(QObject::tr("正在读取原始来源…"), dialog);
    status->setTextFormat(Qt::PlainText); status->setWordWrap(true); layout->addWidget(status);
    auto *scroll = new QScrollArea(dialog); scroll->setWidgetResizable(true); layout->addWidget(scroll);
    auto *contents = new QWidget(scroll); auto *body = new QVBoxLayout(contents); scroll->setWidget(contents);
    auto *network = new QNetworkAccessManager(dialog);
    QUrl endpoint(qEnvironmentVariable("PIXIU_BACKEND_URL", "http://127.0.0.1:8765"));
    endpoint.setPath("/agent/citations" + link.path()); endpoint.setQuery(QString()); endpoint.setFragment(QString());
    auto *reply = network->get(QNetworkRequest(endpoint));
    QTimer::singleShot(15000, reply, [reply]() { if (reply->isRunning()) reply->abort(); });
    QObject::connect(reply, &QNetworkReply::finished, dialog, [=]() {
        if (reply->error() != QNetworkReply::NoError) {
            status->setText(QObject::tr("此来源暂时无法查看，可能已过期、遗忘或不再授权。"));
            reply->deleteLater(); return;
        }
        const auto result = QJsonDocument::fromJson(reply->readAll()).object();
        status->setText(result.value("title").toString());
        if (result.value("recorded_version") != result.value("current_version"))
            status->setText(status->text() + QObject::tr("\n记忆后来有过更新，以下为这次回答引用的原始依据。"));
        for (const auto &entry : result.value("sources").toArray()) {
            const auto raw = entry.toObject().value("raw").toObject();
            auto *title = new QLabel(raw.value("title").toString(), contents);
            title->setTextFormat(Qt::PlainText); title->setWordWrap(true); body->addWidget(title);
            const auto value = raw.value("body");
            const QString text = citationText(value);
            auto *original = new QPlainTextEdit(text, contents); original->setReadOnly(true);
            original->setMinimumHeight(170); body->addWidget(original);
            const auto addImage = [=](const QString &encoded) {
                QPixmap picture;
                if (!picture.loadFromData(QByteArray::fromBase64(encoded.toLatin1()))) return;
                auto *image = new QLabel(contents); image->setPixmap(picture.scaledToWidth(680, Qt::SmoothTransformation));
                image->setAlignment(Qt::AlignCenter); body->addWidget(image);
            };
            addImage(raw.value("original_image").toObject().value("base64").toString());
            for (const auto &source : value.toObject().value("document_sources").toArray()) {
                const auto block = source.toObject().value("block").toObject();
                if (block.value("kind") == "image") addImage(block.value("data_base64").toString());
                else if (!block.value("text").toString().isEmpty()) {
                    auto *sourceText = new QPlainTextEdit(block.value("text").toString(), contents);
                    sourceText->setReadOnly(true); sourceText->setMinimumHeight(170); body->addWidget(sourceText);
                }
            }
        }
        body->addStretch(); reply->deleteLater();
    });
    dialog->show();
    return true;
}
}
