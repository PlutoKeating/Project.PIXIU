#ifndef PIXIU_WRITE_CONTROLLER_H
#define PIXIU_WRITE_CONTROLLER_H

#include <QJsonObject>
#include <QObject>
#include <QString>

class BackendTransport;

// 记忆写入控制器：封装 /memory/write 请求与结果上抛。
class WriteController : public QObject
{
    Q_OBJECT

public:
    explicit WriteController(BackendTransport *transport, QObject *parent = nullptr);

    // 文本录入：source_type=MANUAL_CONFIG。
    void submit(const QString &title,
                const QString &content,
                const QString &scope);

signals:
    void writeAccepted(const QJsonObject &response);
    void writeFailed(const QString &code, const QString &message);

private:
    BackendTransport *m_transport = nullptr;
};

#endif // PIXIU_WRITE_CONTROLLER_H
