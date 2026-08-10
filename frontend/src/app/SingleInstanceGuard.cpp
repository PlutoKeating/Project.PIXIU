#include "app/SingleInstanceGuard.h"

#include <QCoreApplication>
#include <QLocalServer>
#include <QLocalSocket>
#include <QLoggingCategory>

Q_LOGGING_CATEGORY(lcSingleInstance, "pixiu.single-instance")

namespace {
constexpr int kConnectTimeoutMs = 50;
}

SingleInstanceGuard::SingleInstanceGuard(QObject *parent)
    : QObject(parent)
{
}

bool SingleInstanceGuard::tryStart()
{
    const QString name = socketName();

    // 先尝试连接：连接成功说明已有主实例在监听。
    {
        QLocalSocket probe;
        probe.connectToServer(name);
        if (probe.waitForConnected(kConnectTimeoutMs)) {
            qCInfo(lcSingleInstance) << "another instance is running, requesting activation";
            // 连接动作本身即触发主实例的 newConnection → activationRequested。
            return false;
        }
    }

    // 无主实例：清理可能残留的陈旧 socket（例如上次异常退出）。
    QLocalServer::removeServer(name);

    m_server = new QLocalServer(this);
    connect(m_server, &QLocalServer::newConnection,
            this, &SingleInstanceGuard::handleNewConnection);

    if (!m_server->listen(name)) {
        qCWarning(lcSingleInstance)
            << "failed to listen on" << name
            << ":" << m_server->errorString();
        return false;
    }

    qCInfo(lcSingleInstance) << "primary instance listening on" << name;
    return true;
}

void SingleInstanceGuard::stop()
{
    if (m_server) {
        m_server->close();
        m_server->deleteLater();
        m_server = nullptr;
    }
}

void SingleInstanceGuard::handleNewConnection()
{
    if (!m_server) {
        return;
    }
    while (m_server->hasPendingConnections()) {
        QLocalSocket *connection = m_server->nextPendingConnection();
        connection->disconnectFromServer();
        connection->deleteLater();
    }
    qCInfo(lcSingleInstance) << "activation requested by secondary instance";
    emit activationRequested();
}

QString SingleInstanceGuard::socketName() const
{
    // 以应用名 + 用户名命名，避免多用户同机时相互干扰。
    const QString userName = qEnvironmentVariable("USER", QStringLiteral("default"));
    return QStringLiteral("com.kylin.pixiu.frontend.%1").arg(userName);
}
