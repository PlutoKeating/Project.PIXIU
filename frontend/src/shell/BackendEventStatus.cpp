#include "BackendEventStatus.h"
#include "widgets/ContentReveal.h"
#include "widgets/DreamingReviewDialog.h"
#include "services/WebSocketClient.h"
#include <QHBoxLayout>
#include <QLabel>
#include <QPushButton>
#include <QUrl>
#include <QTabWidget>
#include <QRegularExpression>
#include <QTimer>
#include "ForgetPage.h"

namespace pixiu {
BackendEventStatus::BackendEventStatus(const QString &baseUrl, QWidget *parent) : QWidget(parent)
{
    setObjectName(QStringLiteral("backendEventStatus"));
    new ContentReveal(this);
    auto *layout = new QHBoxLayout(this);
    auto *connection = new QLabel(this);
    m_connection = connection;
    connection->setObjectName(QStringLiteral("eventConnection"));
    connection->setTextFormat(Qt::PlainText);
    connection->setWordWrap(true);
    layout->addWidget(connection);
    m_progress = new QLabel(this);
    m_progress->setObjectName(QStringLiteral("dreamingProgress"));
    m_progress->setTextFormat(Qt::PlainText);
    m_progress->setWordWrap(true);
    layout->addWidget(m_progress, 1);
    auto *reportTimer = new QTimer(this);
    reportTimer->setSingleShot(true);
    reportTimer->setInterval(15000);
    connect(reportTimer, &QTimer::timeout, this, [this]() {
        m_progress->clear();
        updateVisibility();
    });
    updateVisibility();
    const QUrl url(baseUrl);
    if (!url.isValid() || url.host().isEmpty() || !url.userInfo().isEmpty()
        || url.hasQuery() || url.hasFragment()
        || (url.scheme() != "http" && url.scheme() != "https")) {
        connection->setText(tr("暂时无法连接记忆服务，请在设置中检查连接。"));
        updateVisibility();
        return;
    }
    auto *reviewDialog = new DreamingReviewDialog(url, this);
    m_reviewDreaming = new QPushButton(tr("查看整理方案"), this);
    m_reviewDreaming->setObjectName("reviewDreamingPlans");
    m_reviewDreaming->hide();
    layout->addWidget(m_reviewDreaming);
    connect(m_reviewDreaming, &QPushButton::clicked, this, [reviewDialog]() {
        reviewDialog->refresh(); reviewDialog->show(); reviewDialog->raise(); reviewDialog->activateWindow();
    });
    connect(reviewDialog, &DreamingReviewDialog::pendingChanged, this, [this](int count) {
        m_reviewDreaming->setVisible(count > 0); updateVisibility();
    });
    reviewDialog->refresh();
    auto *reviewForget = new QPushButton(tr("查看遗忘计划"), this);
    m_reviewForget = reviewForget;
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
        updateVisibility();
    });
    auto *client = new WebSocketClient(this);
    connect(client, &WebSocketClient::connectionStateChanged, this, [this, connection, reviewDialog](ConnectionState state) {
        if (state == ConnectionState::Connected) {
            connection->clear();
            reviewDialog->refresh();
            emit dataChanged(QStringLiteral("reconnected"));
        } else if (state == ConnectionState::Connecting) {
            connection->clear();
        } else {
            connection->setText(tr("正在恢复连接，最新结果稍后自动更新。"));
        }
        updateVisibility();
    });
    connect(client, &WebSocketClient::eventReceived, this, [this, reviewForget, reportTimer, reviewDialog](const QJsonObject &event) {
        const QString name = event.value("event").toString();
        if (name == "dreaming_review") { reviewDialog->refresh(); return; }
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
            else if (status == "awaiting_approval")
                m_progress->setText(tr("资料整理方案等待审批，已保存 %1 条记忆。").arg(saved));
            else if (status == "incomplete")
                m_progress->setText(tr("资料尚未完整整理，已保存 %1 条记忆。").arg(saved));
            else return;
            if (status == "running") reportTimer->stop();
            else reportTimer->start();
            updateVisibility();
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
                updateVisibility();
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
        emit dataChanged(name);
    });
    client->setBackendUrl(url.toString());
    client->connectToBackend();
}
void BackendEventStatus::updateVisibility()
{
    m_connection->setVisible(!m_connection->text().isEmpty());
    m_progress->setVisible(!m_progress->text().isEmpty());
    setVisible(!m_connection->text().isEmpty() || !m_progress->text().isEmpty()
               || (m_reviewForget && !m_reviewForget->isHidden())
               || (m_reviewDreaming && !m_reviewDreaming->isHidden()));
}
}
