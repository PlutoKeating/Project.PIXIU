#include "DeliveryPage.h"
#include "services/HttpBackendTransport.h"
#include <QDate>
#include <QDateEdit>
#include <QJsonArray>
#include <QLabel>
#include <QListWidget>
#include <QPlainTextEdit>
#include <QPushButton>
#include <QVBoxLayout>
#include <QTimer>
#include <QShowEvent>

namespace pixiu {
DeliveryPage::DeliveryPage(QWidget *parent, BackendTransport *transport) : QWidget(parent)
{
    auto *http = transport ? transport : new HttpBackendTransport(this);
    auto *layout = new QVBoxLayout(this);
    auto *intro = new QLabel(tr("近期值得关注的资料，以及每天整理的文件和应用使用情况。"), this);
    intro->setWordWrap(true);
    layout->addWidget(intro);
    auto *insights = new QPushButton(tr("重试读取建议"), this);
    insights->setObjectName(QStringLiteral("deliveryInsights"));
    layout->addWidget(insights);
    auto *items = new QListWidget(this);
    m_items = items;
    items->setObjectName(QStringLiteral("deliveryItems"));
    items->setWordWrap(true);
    items->setAccessibleName(tr("记忆洞察候选"));
    layout->addWidget(items, 1);
    auto *search = new QPushButton(tr("查看相关资料"), this);
    search->setObjectName(QStringLiteral("deliverySearch"));
    layout->addWidget(search);
    auto *dateLabel = new QLabel(tr("日期"), this);
    layout->addWidget(dateLabel);
    auto *datePicker = new QDateEdit(QDate::currentDate(), this);
    datePicker->setObjectName(QStringLiteral("deliveryDate"));
    datePicker->setDisplayFormat(QStringLiteral("yyyy-MM-dd"));
    datePicker->setCalendarPopup(true);
    datePicker->setAccessibleName(tr("采集简报日期"));
    dateLabel->setBuddy(datePicker);
    layout->addWidget(datePicker);
    auto *digest = new QPushButton(tr("重试读取简报"), this);
    digest->setObjectName(QStringLiteral("deliveryDigest"));
    layout->addWidget(digest);
    auto *body = new QPlainTextEdit(this);
    m_body = body;
    body->setObjectName(QStringLiteral("deliveryBody"));
    body->setReadOnly(true);
    layout->addWidget(body, 1);
    auto *status = new QLabel(tr("正在准备简报…"), this);
    m_status = status;
    status->setObjectName(QStringLiteral("deliveryStatus"));
    status->setTextFormat(Qt::PlainText);
    status->setWordWrap(true);
    layout->addWidget(status);
    m_refreshTimer = new QTimer(this);
    m_refreshTimer->setSingleShot(true);
    m_refreshTimer->setInterval(500);
    connect(m_refreshTimer, &QTimer::timeout, this, [=]() {
        if (!isVisible() || m_pending != None || !m_refreshNeeded) return;
        m_refreshNeeded = false;
        m_autoDigest = true;
        insights->click();
    });
    auto controls = [=]() {
        insights->setVisible(insights->property("retryNeeded").toBool());
        digest->setVisible(digest->property("retryNeeded").toBool());
        search->setVisible(items->currentItem());
        scheduleRefresh();
        insights->setEnabled(m_pending == None);
        digest->setEnabled(m_pending == None);
        datePicker->setEnabled(m_pending == None);
        items->setEnabled(m_pending == None);
        search->setEnabled(m_pending == None && items->currentItem());
    };
    connect(datePicker, &QDateEdit::dateChanged, this, [=]() {
        body->clear();
        m_refreshNeeded = true;
        scheduleRefresh();
    });
    connect(items, &QListWidget::currentRowChanged, this, [=]() { controls(); });
    connect(search, &QPushButton::clicked, this, [=]() {
        if (m_pending == None && items->currentItem())
            emit searchRequested(items->currentItem()->data(Qt::UserRole).toString());
    });
    connect(insights, &QPushButton::clicked, this, [=]() {
        if (m_pending != None) return;
        m_refreshNeeded = false;
        insights->setProperty("retryNeeded", false);
        m_pending = Insights;
        m_invalidated = false;
        items->clear();
        status->setText(tr("正在读取洞察…"));
        controls();
        http->deliveryInsights();
    });
    connect(digest, &QPushButton::clicked, this, [=]() {
        if (m_pending != None) return;
        m_refreshNeeded = false;
        digest->setProperty("retryNeeded", false);
        m_pending = Digest;
        m_invalidated = false;
        m_digestDate = datePicker->date().toString(Qt::ISODate);
        body->clear();
        status->setText(tr("正在读取简报…"));
        controls();
        http->deliveryDigest(m_digestDate);
    });
    connect(http, &BackendTransport::insightsResult, this, [=](const QJsonArray &result) {
        if (m_pending != Insights) return;
        m_pending = None;
        if (m_invalidated) { controls(); return; }
        for (const auto &value : result) {
            const auto item = value.toObject();
            if (item.value("title").toString().isEmpty() || !item.value("summary").isString()
                || item.value("knowledge_id").toString().isEmpty() || !item.value("score").isDouble()) {
                items->clear();
                insights->setProperty("retryNeeded", true);
                status->setText(tr("建议暂时未能读取，请重试。"));
                controls();
                return;
            }
            auto *row = new QListWidgetItem(tr("%1\n%2").arg(item.value("title").toString(),
                item.value("summary").toString()), items);
            row->setData(Qt::UserRole, item.value("title").toString());
        }
        status->setText(result.isEmpty() ? tr("最近没有新的建议。")
            : tr("选择一条建议查看相关资料。"));
        controls();
        if (m_autoDigest) { m_autoDigest = false; digest->click(); }
    });
    connect(http, &BackendTransport::digestResult, this, [=](const QJsonObject &result) {
        if (m_pending != Digest) return;
        m_pending = None;
        if (m_invalidated) { controls(); return; }
        const auto date = result.value("date").toString();
        if (!QDate::fromString(date, Qt::ISODate).isValid() || !result.value("summary").isString()) {
            digest->setProperty("retryNeeded", true);
            status->setText(tr("简报暂时未能读取，请重试。"));
        } else if (date != m_digestDate || datePicker->date().toString(Qt::ISODate) != m_digestDate) {
            digest->setProperty("retryNeeded", true);
            status->setText(tr("简报日期不一致，请重试。"));
        } else {
            body->setPlainText(date + QLatin1Char('\n') + result.value("summary").toString());
            status->setText(tr("简报已更新。"));
        }
        controls();
    });
    connect(http, &BackendTransport::errorOccurred, this, [=](const QString &, const QString &message, const QString &) {
        if (m_pending == None) return;
        (m_pending == Insights ? insights : digest)->setProperty("retryNeeded", true);
        m_autoDigest = false;
        m_pending = None;
        if (m_invalidated) { controls(); return; }
        status->setText(tr("暂时未能读取：%1，请重试。").arg(message));
        controls();
    });
    controls();
}
void DeliveryPage::notifyDataChanged()
{
    m_refreshNeeded = true;
    m_invalidated = true;
    m_items->clear();
    m_body->clear();
    m_status->setText(tr("正在更新简报…"));
    scheduleRefresh();
}
void DeliveryPage::scheduleRefresh()
{
    if (m_refreshNeeded && isVisible() && m_pending == None && !m_refreshTimer->isActive())
        m_refreshTimer->start();
}
void DeliveryPage::showEvent(QShowEvent *event)
{
    QWidget::showEvent(event);
    scheduleRefresh();
}
}
