#include "DeliveryPage.h"
#include "services/HttpBackendTransport.h"
#include <QDate>
#include <QJsonArray>
#include <QLabel>
#include <QListWidget>
#include <QPlainTextEdit>
#include <QPushButton>
#include <QVBoxLayout>

namespace pixiu {
DeliveryPage::DeliveryPage(QWidget *parent, BackendTransport *transport) : QWidget(parent)
{
    auto *http = transport ? transport : new HttpBackendTransport(this);
    auto *layout = new QVBoxLayout(this);
    auto *intro = new QLabel(tr("洞察来自本机个人域最近 24 小时的记忆候选，最多显示 3 条；待处理人工冲突可能抑制推荐。简报按后端本地日期汇总采集日志，不是全部记忆统计或模型生成报告。"), this);
    intro->setWordWrap(true);
    layout->addWidget(intro);
    auto *insights = new QPushButton(tr("刷新记忆洞察"), this);
    insights->setObjectName(QStringLiteral("deliveryInsights"));
    layout->addWidget(insights);
    auto *items = new QListWidget(this);
    items->setObjectName(QStringLiteral("deliveryItems"));
    items->setWordWrap(true);
    items->setAccessibleName(tr("记忆洞察候选"));
    layout->addWidget(items, 1);
    auto *search = new QPushButton(tr("按所选标题检索记忆"), this);
    search->setObjectName(QStringLiteral("deliverySearch"));
    layout->addWidget(search);
    auto *digest = new QPushButton(tr("读取今日采集简报"), this);
    digest->setObjectName(QStringLiteral("deliveryDigest"));
    layout->addWidget(digest);
    auto *body = new QPlainTextEdit(this);
    body->setObjectName(QStringLiteral("deliveryBody"));
    body->setReadOnly(true);
    layout->addWidget(body, 1);
    auto *status = new QLabel(tr("请选择读取洞察或简报。"), this);
    status->setObjectName(QStringLiteral("deliveryStatus"));
    status->setTextFormat(Qt::PlainText);
    status->setWordWrap(true);
    layout->addWidget(status);
    auto controls = [=]() {
        insights->setEnabled(m_pending == None);
        digest->setEnabled(m_pending == None);
        items->setEnabled(m_pending == None);
        search->setEnabled(m_pending == None && items->currentItem());
    };
    connect(items, &QListWidget::currentRowChanged, this, [=]() { controls(); });
    connect(search, &QPushButton::clicked, this, [=]() {
        if (m_pending == None && items->currentItem())
            emit searchRequested(items->currentItem()->data(Qt::UserRole).toString());
    });
    connect(insights, &QPushButton::clicked, this, [=]() {
        if (m_pending != None) return;
        m_pending = Insights;
        items->clear();
        status->setText(tr("正在读取洞察…"));
        controls();
        http->deliveryInsights();
    });
    connect(digest, &QPushButton::clicked, this, [=]() {
        if (m_pending != None) return;
        m_pending = Digest;
        body->clear();
        status->setText(tr("正在读取简报…"));
        controls();
        http->deliveryDigest();
    });
    connect(http, &BackendTransport::insightsResult, this, [=](const QJsonArray &result) {
        if (m_pending != Insights) return;
        m_pending = None;
        for (const auto &value : result) {
            const auto item = value.toObject();
            if (item.value("title").toString().isEmpty() || !item.value("summary").isString()
                || item.value("knowledge_id").toString().isEmpty() || !item.value("score").isDouble()) {
                items->clear();
                status->setText(tr("洞察响应包含无效记录，请重试。"));
                controls();
                return;
            }
            auto *row = new QListWidgetItem(tr("%1\n%2\n质量分：%3").arg(item.value("title").toString(),
                item.value("summary").toString()).arg(item.value("score").toDouble(), 0, 'f', 2), items);
            row->setData(Qt::UserRole, item.value("title").toString());
        }
        status->setText(result.isEmpty() ? tr("暂无洞察候选；可能没有近期候选或推荐被冲突抑制，不代表记忆库为空。")
            : tr("洞察已读取。标题检索可能返回多条匹配，不等同于直接打开此知识。"));
        controls();
    });
    connect(http, &BackendTransport::digestResult, this, [=](const QJsonObject &result) {
        if (m_pending != Digest) return;
        m_pending = None;
        const auto date = result.value("date").toString();
        if (!QDate::fromString(date, Qt::ISODate).isValid() || !result.value("summary").isString()) {
            status->setText(tr("简报响应不完整，请重试。"));
        } else {
            body->setPlainText(date + QLatin1Char('\n') + result.value("summary").toString());
            status->setText(tr("已读取后端日期对应的采集简报。"));
        }
        controls();
    });
    connect(http, &BackendTransport::errorOccurred, this, [=](const QString &, const QString &message, const QString &) {
        if (m_pending == None) return;
        m_pending = None;
        status->setText(tr("读取失败：%1。可重试。未将错误显示为空数据。").arg(message));
        controls();
    });
    controls();
}
}
