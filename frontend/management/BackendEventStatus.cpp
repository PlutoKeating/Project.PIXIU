#include "BackendEventStatus.h"
#include "services/WebSocketClient.h"
#include <QHBoxLayout>
#include <QLabel>
#include <QPushButton>
#include <QUrl>

namespace pixiu {
BackendEventStatus::BackendEventStatus(const QString &baseUrl, QWidget *parent) : QWidget(parent)
{
    setObjectName(QStringLiteral("backendEventStatus"));
    auto *layout = new QHBoxLayout(this);
    auto *connection = new QLabel(tr("事件通道尚未连接；不代表服务健康状态。"), this);
    connection->setObjectName(QStringLiteral("eventConnection"));
    connection->setTextFormat(Qt::PlainText);
    connection->setWordWrap(true);
    layout->addWidget(connection);
    m_notice = new QLabel(this);
    m_notice->setObjectName(QStringLiteral("eventChanges"));
    m_notice->setTextFormat(Qt::PlainText);
    m_notice->setWordWrap(true);
    layout->addWidget(m_notice, 1);
    m_dismiss = new QPushButton(tr("清除提示"), this);
    m_dismiss->setObjectName(QStringLiteral("eventDismiss"));
    layout->addWidget(m_dismiss);
    connect(m_dismiss, &QPushButton::clicked, this, [this]() {
        m_changed.clear();
        updateNotice();
    });
    updateNotice();
    const QUrl url(baseUrl);
    if (!url.isValid() || url.host().isEmpty() || !url.userInfo().isEmpty()
        || url.hasQuery() || url.hasFragment()
        || (url.scheme() != "http" && url.scheme() != "https")) {
        connection->setText(tr("事件地址无效，未连接；请检查后端配置。"));
        return;
    }
    auto *client = new WebSocketClient(this);
    connect(client, &WebSocketClient::connectionStateChanged, this, [this, connection](ConnectionState state) {
        if (state == ConnectionState::Connected) {
            connection->setText(tr("事件通道已连接（不代表服务健康）。"));
            // The protocol has no replay cursor: reconnect cannot prove freshness.
            m_changed.insert(tr("连接恢复后的各页面"));
            updateNotice();
        } else if (state == ConnectionState::Connecting) {
            connection->setText(tr("事件通道正在连接…"));
        } else {
            connection->setText(tr("事件通道未连接，将自动重试；页面可能不是最新数据。"));
        }
    });
    connect(client, &WebSocketClient::eventReceived, this, [this](const QJsonObject &event) {
        const QString name = event.value("event").toString();
        QString page;
        if (name == "memory_ready" || name == "forget_confirmation") page = tr("记忆");
        else if (name == "conflict_detected") page = tr("偏好与审计");
        else if (name == "sync_event" || name == "pair_request") page = tr("设备");
        else if (name == "capture_event") page = tr("采集与隐私");
        if (page.isEmpty()) return;
        m_changed.insert(page);
        updateNotice();
    });
    client->setBackendUrl(url.toString());
    client->connectToBackend();
}
void BackendEventStatus::updateNotice()
{
    QStringList pages = m_changed.values();
    pages.sort();
    m_notice->setText(pages.isEmpty() ? QString() : tr("请刷新核对：%1。提示不会执行操作或覆盖未保存输入。")
        .arg(pages.join(QStringLiteral("、"))));
    m_dismiss->setEnabled(!pages.isEmpty());
}
}
