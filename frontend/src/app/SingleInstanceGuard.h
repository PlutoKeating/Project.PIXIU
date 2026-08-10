#ifndef PIXIU_SINGLE_INSTANCE_GUARD_H
#define PIXIU_SINGLE_INSTANCE_GUARD_H

#include <QObject>
#include <QString>

class QLocalServer;
class QLocalSocket;

// 单实例守护：通过命名 QLocalServer 检测并唤醒已有实例。
//
// 行为约定：
//   - 首次启动（无其它实例）：tryStart() 返回 true，本进程成为主实例；
//   - 重复启动：tryStart() 返回 false，并向已有实例发送激活请求；
//   - 异常退出后残留 socket：自动清理陈旧 socket 后重新监听。
class SingleInstanceGuard : public QObject
{
    Q_OBJECT

public:
    explicit SingleInstanceGuard(QObject *parent = nullptr);

    // 尝试成为主实例。true=本进程接管；false=已有实例在运行。
    bool tryStart();

    // 停止监听并释放 socket（应用退出时调用）。
    void stop();

signals:
    // 已有实例被重复启动时触发，用于唤起主窗口。
    void activationRequested();

private:
    void handleNewConnection();

    QString socketName() const;

    QLocalServer *m_server = nullptr;
};

#endif // PIXIU_SINGLE_INSTANCE_GUARD_H
