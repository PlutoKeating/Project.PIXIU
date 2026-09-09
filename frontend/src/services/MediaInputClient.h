#pragma once
#include <QObject>
#include <QNetworkAccessManager>
#include <QNetworkRequest>
#include <QJsonArray>
#include <QStringList>
namespace pixiu {
class MediaInputClient : public QObject {
    Q_OBJECT
public:
    explicit MediaInputClient(QObject *parent = nullptr) : QObject(parent) {}
    void prepare(const QNetworkRequest &runtime, const QStringList &paths);
signals:
    void prepared(const QJsonArray &parts);
    void failed(const QString &message);
private:
    void next();
    QNetworkAccessManager m_network;
    QNetworkRequest m_runtime;
    QStringList m_paths;
    QJsonArray m_parts;
};
}
