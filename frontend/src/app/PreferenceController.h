#ifndef PIXIU_PREFERENCE_CONTROLLER_H
#define PIXIU_PREFERENCE_CONTROLLER_H

#include <QJsonObject>
#include <QObject>
#include <QString>

class BackendTransport;

// 偏好历史控制器：GET /preference/{id}/history 的加载与结果上抛。
class PreferenceController : public QObject
{
    Q_OBJECT

public:
    explicit PreferenceController(BackendTransport *transport, QObject *parent = nullptr);

    void loadHistory(const QString &preferenceId);

signals:
    void historyLoaded(const QJsonObject &response);
    void failed(const QString &code, const QString &message);

private:
    BackendTransport *m_transport = nullptr;
    QString m_pendingId;
};

#endif // PIXIU_PREFERENCE_CONTROLLER_H
