#include "DreamingReviewDialog.h"
#include <QHBoxLayout>
#include <QVBoxLayout>
#include <QLabel>
#include <QListWidget>
#include <QPlainTextEdit>
#include <QPushButton>
#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QJsonDocument>
#include <QJsonObject>
#include <QTimer>
namespace pixiu {
DreamingReviewDialog::DreamingReviewDialog(const QUrl &endpoint, QWidget *parent)
    : QDialog(parent), m_endpoint(endpoint), m_network(new QNetworkAccessManager(this))
{
    setWindowTitle(tr("资料整理方案"));
    setObjectName("dreamingReviewDialog");
    resize(880, 580);
    auto *layout = new QVBoxLayout(this);
    auto *intro = new QLabel(tr("助手根据新资料提出了以下整理方案。核对原内容与新内容后，批准执行或保留原内容。"), this);
    intro->setWordWrap(true); layout->addWidget(intro);
    m_plans = new QListWidget(this); m_plans->setMaximumHeight(140); layout->addWidget(m_plans);
    auto *columns = new QHBoxLayout;
    m_before = new QPlainTextEdit(this); m_before->setReadOnly(true);
    m_before->setAccessibleName(tr("原内容"));
    m_after = new QPlainTextEdit(this); m_after->setReadOnly(true);
    m_after->setAccessibleName(tr("整理后内容"));
    for (auto pair : {qMakePair(tr("原内容"), m_before), qMakePair(tr("整理后内容"), m_after)}) {
        auto *column = new QVBoxLayout; column->addWidget(new QLabel(pair.first, this));
        column->addWidget(pair.second); columns->addLayout(column);
    }
    layout->addLayout(columns, 1);
    m_status = new QLabel(this); m_status->setWordWrap(true); layout->addWidget(m_status);
    auto *actions = new QHBoxLayout;
    auto *reload = new QPushButton(tr("重新读取"), this);
    m_reject = new QPushButton(tr("保留原内容"), this);
    m_approve = new QPushButton(tr("批准更正"), this);
    actions->addWidget(reload); actions->addStretch(); actions->addWidget(m_reject); actions->addWidget(m_approve);
    layout->addLayout(actions);
    connect(reload, &QPushButton::clicked, this, &DreamingReviewDialog::refresh);
    connect(m_plans, &QListWidget::currentRowChanged, this, [this]() { selected(); });
    connect(m_reject, &QPushButton::clicked, this, [this]() { decide(false); });
    connect(m_approve, &QPushButton::clicked, this, [this]() { decide(true); });
    selected();
}
void DreamingReviewDialog::selected()
{
    const int index = m_plans->currentRow();
    const auto value = (index >= 0 && index < m_records.size() ? m_records.at(index).toObject() : QJsonObject());
    m_approve->setEnabled(!m_busy && value.value("status") == "pending");
    m_reject->setEnabled(!m_busy && index >= 0 && value.value("status") != "executing");
    const bool merge = value.value("operation") == "merge";
    m_approve->setText(merge ? tr("批准合并") : tr("批准更正"));
    const auto before = value.value("before").toObject();
    const auto body = before.value("body").toObject();
    QString text = body.value("content").toString(body.value("text").toString());
    if (text.isEmpty() && !body.isEmpty()) text = QString::fromUtf8(QJsonDocument(body).toJson(QJsonDocument::Indented));
    QString originalText = before.value("title").toString() + "\n\n" + text;
    if (merge) {
        QStringList originals;
        for (const auto &entry : value.value("originals").toArray()) {
            const auto record = entry.toObject();
            const auto content = record.value("body").toObject();
            QString details = content.value("content").toString(content.value("text").toString());
            if (details.isEmpty()) details = QString::fromUtf8(QJsonDocument(content).toJson(QJsonDocument::Indented));
            originals.append(record.value("title").toString() + "\n" + details);
        }
        originalText = tr("以下记录将合并为右侧的一条记忆，原始来源会保留。\n\n") + originals.join("\n\n────────\n\n");
    }
    m_before->setPlainText(originalText);
    m_after->setPlainText(value.value("title").toString() + "\n\n" + value.value("text").toString());
}
void DreamingReviewDialog::refresh()
{
    if (m_busy) return;
    m_busy = true; selected();
    auto url = m_endpoint; url.setPath("/dreaming/plans"); url.setQuery(QString());
    auto *reply = m_network->get(QNetworkRequest(url));
    QTimer::singleShot(15000, reply, [reply]() { if (reply->isRunning()) reply->abort(); });
    connect(reply, &QNetworkReply::finished, this, [this, reply]() {
        m_busy = false;
        if (reply->error() != QNetworkReply::NoError) {
            m_status->setText(tr("整理方案暂时无法读取，请稍后重试。"));
        } else {
            m_records = QJsonDocument::fromJson(reply->readAll()).object().value("plans").toArray();
            m_plans->clear();
            for (const auto &entry : m_records) {
                const auto plan = entry.toObject();
                m_plans->addItem(plan.value("title").toString() + (plan.value("status") == "failed" ? tr(" · 原内容已变化或执行失败") : QString()));
            }
            if (!m_records.isEmpty()) m_plans->setCurrentRow(0);
            m_status->setText(m_records.isEmpty() ? tr("暂无待审批的整理方案。") : tr("批准前请核对整理内容。"));
            emit pendingChanged(m_records.size());
        }
        reply->deleteLater(); selected();
    });
}
void DreamingReviewDialog::decide(bool approve)
{
    if (m_busy || m_plans->currentRow() < 0) return;
    const auto plan = m_records.at(m_plans->currentRow()).toObject();
    m_busy = true; selected();
    auto url = m_endpoint; url.setPath("/dreaming/plans/" + plan.value("plan_id").toString() + "/decision"); url.setQuery(QString());
    QNetworkRequest request(url); request.setHeader(QNetworkRequest::ContentTypeHeader, "application/json");
    auto *reply = m_network->post(request, QJsonDocument(QJsonObject{{"approve", approve}}).toJson(QJsonDocument::Compact));
    QTimer::singleShot(60000, reply, [reply]() { if (reply->isRunning()) reply->abort(); });
    connect(reply, &QNetworkReply::finished, this, [this, reply]() {
        m_busy = false;
        const bool ok = reply->error() == QNetworkReply::NoError;
        reply->deleteLater();
        if (ok) refresh();
        else { m_status->setText(tr("方案未完成。原内容可能已变化，请重新读取并核对。")); selected(); }
    });
}
}
