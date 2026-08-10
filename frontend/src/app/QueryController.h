#ifndef PIXIU_QUERY_CONTROLLER_H
#define PIXIU_QUERY_CONTROLLER_H

#include <QObject>
#include <QString>

#include "models/MemoryAtom.h"

class BackendTransport;

// 查询状态机：加载/取消/超时/失败/重试。
//
// 职责：
//   - 管理查询序号，新查询使旧查询失效（取消语义）；
//   - 将 /memory/query 原始响应解析为 MemoryAtom 后以语义信号上抛；
//   - 失败时携带原文与错误信息，供 UI 保留输入重试。
// 本类不直接操作 Widget，UI 通过信号完成展示。
class QueryController : public QObject
{
    Q_OBJECT

public:
    explicit QueryController(BackendTransport *transport, QObject *parent = nullptr);

    // 提交新查询；若已有查询在途则自动取消。
    void submit(const QString &text);

    // 由 transport 的 queryResult / errorOccurred 转发。
    void handleQueryResult(quint64 requestId, const QJsonObject &atom);
    void handleQueryError(quint64 requestId, const QString &code, const QString &message);

signals:
    void userMessageReady(const QString &text);
    void thinkingChanged(bool thinking);
    void answerReady(const MemoryAtom &atom);
    void emptyResultReady();
    void queryFailed(const QString &text, const QString &code, const QString &message);

private:
    BackendTransport *m_transport = nullptr;
    int m_sequence = 0;
    int m_pendingSequence = -1;
    quint64 m_pendingRequestId = 0;
    QString m_pendingText;
};

#endif // PIXIU_QUERY_CONTROLLER_H
