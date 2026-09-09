#include "BackendEventStatus.h"
#include "services/WebSocketClient.h"
#include <QHBoxLayout>
#include <QLabel>
#include <QPushButton>
#include <QUrl>
#include <QTabWidget>
#include <QRegularExpression>
#include "ForgetPage.h"

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
    m_progress = new QLabel(this);
    m_progress->setObjectName(QStringLiteral("dreamingProgress"));
    m_progress->setTextFormat(Qt::PlainText);
    m_progress->setWordWrap(true);
    layout->addWidget(m_progress, 1);
    m_dismiss = new QPushButton(tr("清除提示"), this);
    m_dismiss->setObjectName(QStringLiteral("eventDismiss"));
    layout->addWidget(m_dismiss);
    connect(m_dismiss, &QPushButton::clicked, this, [this]() {
        m_changed.clear();
        m_progress->clear();
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
    auto *reviewForget = new QPushButton(tr("确认助手遗忘请求"), this);
    reviewForget->setObjectName("reviewAgentForget");
    reviewForget->hide();
    layout->addWidget(reviewForget);
    connect(reviewForget, &QPushButton::clicked, this, [this, reviewForget]() {
        auto *page = window()->findChild<ForgetPage *>();
        if (!page || !page->setAgentIntent(reviewForget->property("command").toString(),
                                           reviewForget->property("scope").toString())) return;
        QWidget *child = page;
        for (auto *parent = child->parentWidget(); parent; child = parent, parent = parent->parentWidget()) {
            if (auto *tabs = qobject_cast<QTabWidget *>(parent->parentWidget())) {
                const int index = tabs->indexOf(child);
                if (index >= 0) tabs->setCurrentIndex(index);
            }
        }
        reviewForget->hide();
    });
    auto *client = new WebSocketClient(this);
    connect(client, &WebSocketClient::connectionStateChanged, this, [this, connection](ConnectionState state) {
        if (state == ConnectionState::Connected) {
            connection->setText(tr("事件通道已连接（不代表服务健康）。"));
            // The protocol has no replay cursor: reconnect cannot prove freshness.
            m_changed.insert(tr("连接恢复后的各页面"));
            updateNotice();
            emit dataChanged(QStringLiteral("reconnected"));
        } else if (state == ConnectionState::Connecting) {
            connection->setText(tr("事件通道正在连接…"));
        } else {
            connection->setText(tr("事件通道未连接，将自动重试；页面可能不是最新数据。"));
        }
    });
    connect(client, &WebSocketClient::eventReceived, this, [this, reviewForget](const QJsonObject &event) {
        const QString name = event.value("event").toString();
        if (name == "dreaming_progress") {
            const auto data = event.value("data").toObject();
            const auto status = data.value("status").toString();
            const int processed = data.value("processed_blocks").toInt(-1);
            const int total = data.value("total_blocks").toInt(-1);
            const int saved = data.value("saved_count").toInt(-1);
            if (processed < 0 || total < processed || saved < 0) return;
            if (status == "running")
                m_progress->setText(tr("正在整理资料（%1%），已保存 %2 条记忆。")
                    .arg(total ? qRound(100.0 * processed / total) : 0).arg(saved));
            else if (status == "completed")
                m_progress->setText(tr("资料整理完成，已保存 %1 条记忆。").arg(saved));
            else if (status == "incomplete")
                m_progress->setText(tr("资料尚未完整整理，已保存 %1 条记忆。").arg(saved));
            else return;
            m_dismiss->setEnabled(true);
            emit dataChanged(name);
            return;
        }
        if (name == "forget_requested") {
            const auto data = event.value("data").toObject();
            const auto command = data.value("command").toString();
            const auto scope = data.value("scope").toString();
            if (!command.isEmpty() && command.size() <= 4096
                && QRegularExpression("^(user|shared):[A-Za-z0-9._-]+$").match(scope).hasMatch()) {
                reviewForget->setProperty("command", command);
                reviewForget->setProperty("scope", scope);
                reviewForget->show();
            }
            return;
        }
        QString page;
        if (name == "memory_ready" || name == "forget_confirmation") page = tr("记忆");
        else if (name == "conflict_detected") page = tr("偏好与审计");
        else if (name == "sync_event" || name == "pair_request") page = tr("设备");
        else if (name == "capture_event") page = tr("采集与隐私");
        if (page.isEmpty()) return;
        const QString severity = event.value("data").toObject().value("severity").toString().trimmed().toLower();
        if (name == "conflict_detected" && (severity == "high" || severity == "critical")
            && (!m_lastAttention.isValid() || m_lastAttention.elapsed() >= 60000)) {
            m_lastAttention.start();
            emit conflictAttentionRequested(); // no event text, values or IDs cross this boundary
        }
        m_changed.insert(page);
        updateNotice();
        emit dataChanged(name);
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
    m_dismiss->setEnabled(!pages.isEmpty() || !m_progress->text().isEmpty());
}
}
