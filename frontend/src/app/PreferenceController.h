#ifndef PIXIU_PREFERENCE_CONTROLLER_H
#define PIXIU_PREFERENCE_CONTROLLER_H

#include <QJsonArray>
#include <QJsonObject>
#include <QObject>
#include <QString>
#include <QStringList>

class BackendTransport;

// 偏好历史控制器：GET /preference/{id}/history 的加载与结果上抛。
class PreferenceController : public QObject
{
    Q_OBJECT

public:
    explicit PreferenceController(BackendTransport *transport, QObject *parent = nullptr);

    void loadHistory(const QString &preferenceId);
    // 偏好列表：GET /preferences（scope 可空）。
    void loadList(const QString &scope = QString());
    // 偏好提取：POST /preference/extract（evidence_ids 非空且无在途提取时放行）。
    void extract(const QStringList &evidenceIds);

signals:
    void historyLoaded(const QJsonObject &response);
    void listLoaded(const QJsonArray &preferences);
    void extracted(int count, int latencyMs);
    void extractFailed(const QString &code, const QString &message);
    void failed(const QString &code, const QString &message);

private:
    BackendTransport *m_transport = nullptr;
    QString m_pendingId;
    bool m_listPending = false;
    bool m_extractPending = false;
};

#endif // PIXIU_PREFERENCE_CONTROLLER_H
