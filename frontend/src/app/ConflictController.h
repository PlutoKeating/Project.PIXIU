#ifndef PIXIU_CONFLICT_CONTROLLER_H
#define PIXIU_CONFLICT_CONTROLLER_H

#include <QJsonArray>
#include <QObject>
#include <QString>

class BackendTransport;

// 冲突审计控制器：GET /conflicts 的加载与结果上抛。
class ConflictController : public QObject
{
    Q_OBJECT

public:
    explicit ConflictController(BackendTransport *transport, QObject *parent = nullptr);

    // 拉取冲突审计列表（幂等；面板每次打开时刷新）。
    void refresh();

signals:
    void conflictsLoaded(const QJsonArray &conflicts);
    void failed(const QString &code, const QString &message);

private:
    BackendTransport *m_transport = nullptr;
    bool m_inFlight = false;
};

#endif // PIXIU_CONFLICT_CONTROLLER_H
