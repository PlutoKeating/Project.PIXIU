#ifndef PIXIU_FORGET_CONTROLLER_H
#define PIXIU_FORGET_CONTROLLER_H

#include <QJsonObject>
#include <QObject>
#include <QString>

class BackendTransport;

// 自然语言遗忘两段式确认控制器：
//   1) requestConfirmation → transport.forget(command, false) → confirmationReady；
//   2) confirm → transport.forget(command, true) → forgotten / failed。
// 取消后清空待确认指令，不会误发第二阶段请求。
class ForgetController : public QObject
{
    Q_OBJECT

public:
    explicit ForgetController(BackendTransport *transport, QObject *parent = nullptr);

    // 遗忘指令识别（“忘记/遗忘/忘了”开头）。
    static bool isForgetIntent(const QString &text);

    // 第一阶段：请求后端返回匹配目标与级联影响（confirm=false）。
    void requestConfirmation(const QString &command);
    // 第二阶段：确认执行（confirm=true）。
    void confirm();
    // 用户取消：丢弃待确认指令。
    void cancel();

signals:
    // 第一阶段结果（targets + cascade + irreversible）。
    void confirmationReady(const QString &command, const QJsonObject &response);
    // 第二阶段结果（status=forgotten + forgotten_ids）。
    void forgotten(const QJsonObject &response);
    void failed(const QString &code, const QString &message);

private:
    void handleForgetResult(const QJsonObject &response);

    BackendTransport *m_transport = nullptr;
    QString m_pendingCommand;
};

#endif // PIXIU_FORGET_CONTROLLER_H
