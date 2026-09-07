#include "MemoryWorkspace.h"
#include "services/HttpBackendTransport.h"
#include <QComboBox>
#include <QHBoxLayout>
#include <QJsonArray>
#include <QLabel>
#include <QLineEdit>
#include <QListWidget>
#include <QPlainTextEdit>
#include <QPushButton>
#include <QVBoxLayout>

namespace pixiu {
MemoryWorkspace::MemoryWorkspace(QWidget *parent, BackendTransport *transport)
    : QWidget(parent), m_transport(transport ? transport : new HttpBackendTransport(this))
{
    setObjectName(QStringLiteral("memoryWorkspace"));
    auto *layout = new QVBoxLayout(this);
    layout->setContentsMargins(20, 16, 20, 16);
    auto *title = new QLabel(tr("记忆工作区"), this);
    title->setObjectName(QStringLiteral("brandTitle"));
    layout->addWidget(title);
    auto *intro = new QLabel(tr("直接检索已保存的记忆并查看来源，无需配置大模型。"), this);
    intro->setWordWrap(true);
    layout->addWidget(intro);
    auto *row = new QHBoxLayout;
    m_query = new QLineEdit(this);
    m_query->setObjectName(QStringLiteral("memoryQuery"));
    m_query->setPlaceholderText(tr("输入想查找的内容"));
    m_query->setAccessibleName(tr("记忆检索内容"));
    m_scope = new QComboBox(this);
    m_scope->setObjectName(QStringLiteral("memoryScope"));
    m_scope->setAccessibleName(tr("检索范围"));
    m_scope->addItem(tr("全部范围"), QString());
    m_scope->addItem(tr("个人"), QStringLiteral("user:local"));
    m_scope->addItem(tr("家庭共享"), QStringLiteral("shared:home"));
    m_search = new QPushButton(tr("检索"), this);
    m_search->setObjectName(QStringLiteral("memorySearch"));
    row->addWidget(m_query, 1);
    row->addWidget(m_scope);
    row->addWidget(m_search);
    layout->addLayout(row);
    m_status = new QLabel(tr("输入关键词开始检索。"), this);
    m_status->setObjectName(QStringLiteral("memoryStatus"));
    m_status->setTextFormat(Qt::PlainText);
    m_status->setWordWrap(true);
    layout->addWidget(m_status);
    m_answer = new QPlainTextEdit(this);
    m_answer->setObjectName(QStringLiteral("memoryAnswer"));
    m_answer->setReadOnly(true);
    m_answer->setAccessibleName(tr("记忆检索结果"));
    layout->addWidget(m_answer, 2);
    m_sources = new QListWidget(this);
    m_sources->setObjectName(QStringLiteral("memorySources"));
    m_sources->setAccessibleName(tr("结果来源，选择以阅读证据"));
    m_sources->setMaximumHeight(100);
    layout->addWidget(m_sources);
    m_detailMeta = new QLabel(this);
    m_detailMeta->setWordWrap(true);
    m_detailMeta->setTextFormat(Qt::PlainText);
    layout->addWidget(m_detailMeta);
    m_detail = new QPlainTextEdit(this);
    m_detail->setObjectName(QStringLiteral("memoryEvidence"));
    m_detail->setReadOnly(true);
    m_detail->setAccessibleName(tr("原始证据正文"));
    layout->addWidget(m_detail, 2);
    connect(m_search, &QPushButton::clicked, this, &MemoryWorkspace::search);
    connect(m_query, &QLineEdit::returnPressed, this, &MemoryWorkspace::search);
    connect(m_scope, QOverload<int>::of(&QComboBox::currentIndexChanged), this, [this]() {
        clearResult();
        m_status->setText(tr("范围已切换，请重新检索。"));
    });
    connect(m_transport, &BackendTransport::queryResult, this,
            [this](quint64 id, const QJsonObject &result) {
        if (!m_request || id != m_request) return;
        m_request = 0;
        m_search->setEnabled(true);
        const QString answer = result.value(QStringLiteral("answer")).toString();
        m_answer->setPlainText(answer);
        m_status->setText(answer.isEmpty() ? tr("没有找到匹配的记忆。") : tr("检索完成，选择来源查看证据。"));
        for (const auto &value : result.value(QStringLiteral("source_evidence")).toArray()) {
            const QString source = value.toString();
            if (source.isEmpty()) continue;
            auto *item = new QListWidgetItem(tr("查看来源 %1").arg(m_sources->count() + 1), m_sources);
            item->setData(Qt::UserRole, source);
        }
    });
    connect(m_transport, &BackendTransport::queryFailed, this,
            [this](quint64 id, const QString &, const QString &message) {
        if (!m_request || id != m_request) return;
        m_request = 0;
        m_search->setEnabled(true);
        m_status->setText(tr("检索失败：%1。可再次点击检索重试。").arg(message));
    });
    connect(m_sources, &QListWidget::currentItemChanged, this,
            [this](QListWidgetItem *item) {
        if (!item || m_evidenceBusy) return;
        m_evidenceBusy = true;
        m_sources->setEnabled(false);
        m_search->setEnabled(false);
        m_scope->setEnabled(false);
        m_evidence = item->data(Qt::UserRole).toString();
        m_detail->clear();
        m_detailMeta->setText(tr("正在加载证据…"));
        m_transport->evidenceDetail(m_evidence);
    });
    connect(m_transport, &BackendTransport::evidenceDetailResult, this,
            [this](const QJsonObject &evidence) {
        if (!m_evidenceBusy) return;
        m_evidenceBusy = false;
        m_sources->setEnabled(true);
        m_search->setEnabled(true);
        m_scope->setEnabled(true);
        if (evidence.value(QStringLiteral("id")).toString() != m_evidence) {
            m_detailMeta->setText(tr("证据响应与所选来源不一致，请重新选择来源。"));
            m_sources->setCurrentRow(-1);
            return;
        }
        const QJsonObject raw = evidence.value(QStringLiteral("raw")).toObject();
        const QString body = raw.value(QStringLiteral("body")).toString(raw.value(QStringLiteral("text")).toString());
        m_detailMeta->setText(tr("%1\n来源：%2 · 范围：%3 · 质量：%4")
            .arg(raw.value(QStringLiteral("title")).toString(tr("原始证据")),
                 evidence.value(QStringLiteral("source_type")).toString(),
                 evidence.value(QStringLiteral("scope")).toString())
            .arg(evidence.value(QStringLiteral("quality_score")).toDouble(), 0, 'f', 2));
        m_detail->setPlainText(body.isEmpty() ? tr("此证据没有可显示的文本正文。") : body);
    });
    connect(m_transport, &BackendTransport::errorOccurred, this,
            [this](const QString &, const QString &message, const QString &) {
        if (!m_evidenceBusy) return;
        m_evidenceBusy = false;
        m_sources->setEnabled(true);
        m_search->setEnabled(true);
        m_scope->setEnabled(true);
        m_sources->setCurrentRow(-1);
        m_detailMeta->setText(tr("证据加载失败：%1。重新选择来源可重试。").arg(message));
    });
}

void MemoryWorkspace::clearResult()
{
    m_request = 0;
    m_evidence.clear();
    m_answer->clear();
    m_sources->clear();
    m_detail->clear();
    m_detailMeta->clear();
    m_search->setEnabled(true);
}

void MemoryWorkspace::search()
{
    if (m_request || m_evidenceBusy || m_query->text().trimmed().isEmpty()) return;
    clearResult();
    QJsonObject hint{{QStringLiteral("top_k"), 5}};
    if (!m_scope->currentData().toString().isEmpty())
        hint.insert(QStringLiteral("scope"), m_scope->currentData().toString());
    m_status->setText(tr("正在检索…"));
    m_search->setEnabled(false);
    m_request = m_transport->queryMemory(m_query->text().trimmed(), hint);
}
}
