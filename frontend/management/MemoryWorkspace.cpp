#include "MemoryWorkspace.h"
#include "MemoryScopes.h"
#include "MemoryWriteDialog.h"
#include "MemoryEditDialog.h"
#include "MemoryAudit.h"
#include "DeliveryPage.h"
#include "ForgetPage.h"
#include "services/HttpBackendTransport.h"
#include <QComboBox>
#include <QCheckBox>
#include <QJsonDocument>
#include <QHBoxLayout>
#include <QJsonArray>
#include <QLabel>
#include <QLineEdit>
#include <QListWidget>
#include <QPlainTextEdit>
#include <QPushButton>
#include <QVBoxLayout>
#include <QTabWidget>
#include <QSet>
#include <QRegularExpression>
#include <functional>

namespace pixiu {
namespace {
QString readableEvidence(const QJsonObject &raw)
{
    QJsonObject fields = raw;
    const QJsonValue body = fields.value("body");
    QString text = body.toString();
    if (body.isObject()) {
        text = body.toObject().value("text").toString();
        if (text.isEmpty()) text = body.toObject().value("content").toString();
    }
    if (text.isEmpty()) text = raw.value("text").toString();
    if (fields.value("title").isString()) fields.remove("title");
    if (fields.value("text").isString() && fields.value("text").toString() == text)
        fields.remove("text");
    if (body.isString()) fields.remove("body");
    else if (body.isObject()) {
        auto content = body.toObject();
        for (const QString &key : {QStringLiteral("text"), QStringLiteral("content")})
            if (content.value(key).isString() && content.value(key).toString() == text)
                content.remove(key);
        if (content.isEmpty()) fields.remove("body");
        else fields.insert("body", content);
    }
    // Keep the normal reader selectable plain text, never HTML or executable
    // content. Bound the expanded representation; the advanced view stays exact.
    QString result = text.left(65536);
    bool limited = text.size() > 65536;
    int remaining = 256;
    if (!fields.isEmpty() && !result.isEmpty())
        result += QStringLiteral("\n\n") + MemoryWorkspace::tr("结构化内容") + QLatin1Char('\n');
    std::function<void(const QString &, const QJsonValue &, int)> append;
    append = [&](const QString &name, const QJsonValue &value, int depth) {
        if (remaining == 0 || depth > 8 || result.size() >= 65536) {
            limited = true;
            return;
        }
        --remaining;
        QString scalar;
        if (value.isString()) scalar = value.toString();
        else if (value.isBool()) scalar = value.toBool() ? QStringLiteral("true") : QStringLiteral("false");
        else if (value.isDouble()) scalar = QString::number(value.toDouble(), 'g', 17);
        else if (value.isNull()) scalar = QStringLiteral("null");
        else if (value.isObject() && value.toObject().isEmpty()) scalar = MemoryWorkspace::tr("（空对象）");
        else if (value.isArray() && value.toArray().isEmpty()) scalar = MemoryWorkspace::tr("（空列表）");
        const QString indent(depth * 2, QLatin1Char(' '));
        scalar.replace(QStringLiteral("\n"), QStringLiteral("\n") + indent + QStringLiteral("  "));
        const QString line = indent + name + QStringLiteral("：") + scalar + QLatin1Char('\n');
        const int room = qMax(0, 65536 - result.size());
        result += line.left(room);
        limited |= line.size() > room;
        if (value.isObject()) {
            const auto object = value.toObject();
            for (auto it = object.begin(); it != object.end(); ++it) {
                append(it.key(), it.value(), depth + 1);
                if (!remaining || result.size() >= 65536) break;
            }
        } else if (value.isArray()) {
            const auto array = value.toArray();
            for (int i = 0; i < array.size(); ++i) {
                append(QStringLiteral("[%1]").arg(i + 1), array.at(i), depth + 1);
                if (!remaining || result.size() >= 65536) break;
            }
        }
    };
    for (auto it = fields.begin(); it != fields.end(); ++it) {
        append(it.key(), it.value(), 0);
        if (!remaining || result.size() >= 65536) break;
    }
    if (limited || remaining == 0 || result.size() >= 65536)
        result += QStringLiteral("\n") + MemoryWorkspace::tr("内容较大，部分字段未展开；完整内容见高级原始数据。");
    if (result.isEmpty()) return MemoryWorkspace::tr("此证据没有可展示的正文或结构化字段。");
    if (!fields.isEmpty() && result.endsWith(QLatin1Char('\n'))) result.chop(1);
    return result;
}
}
MemoryWorkspace::MemoryWorkspace(QWidget *parent, BackendTransport *transport)
    : QWidget(parent), m_transport(transport ? transport : new HttpBackendTransport(this))
{
    setObjectName(QStringLiteral("memoryWorkspace"));
    auto *outer = new QVBoxLayout(this);
    outer->setContentsMargins(0, 0, 0, 0);
    auto *tabs = new QTabWidget(this);
    m_tabs = tabs;
    outer->addWidget(tabs);
    auto *queryPage = new QWidget(tabs);
    auto *layout = new QVBoxLayout(queryPage);
    tabs->addTab(queryPage, tr("检索与录入"));
    auto *delivery = new DeliveryPage(tabs);
    tabs->addTab(delivery, tr("洞察与简报"));
    connect(delivery, &DeliveryPage::searchRequested, this, [this, tabs, queryPage](const QString &text) {
        if (m_request || m_evidenceBusy) return;
        tabs->setCurrentWidget(queryPage);
        m_scope->setCurrentIndex(1);
        m_query->setText(text);
        search();
    });
    m_audit = new MemoryAudit(tabs);
    tabs->addTab(m_audit, tr("偏好与审计"));
    auto *forget = new ForgetPage(tabs);
    tabs->addTab(forget, tr("安全遗忘"));
    connect(forget, &ForgetPage::memoryForgotten, this, &MemoryWorkspace::clearResult);
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
    populateMemoryScopes(m_scope, true);
    m_search = new QPushButton(tr("检索"), this);
    m_search->setObjectName(QStringLiteral("memorySearch"));
    row->addWidget(m_query, 1);
    row->addWidget(m_scope);
    row->addWidget(m_search);
    auto *write = new QPushButton(tr("录入记忆"), this);
    write->setObjectName(QStringLiteral("memoryWrite"));
    row->addWidget(write);
    auto *writeDialog = new MemoryWriteDialog(this);
    m_edit = new QPushButton(tr("编辑命中记忆"), this);
    m_edit->setObjectName("memoryEdit");
    m_edit->setToolTip(tr("选择个人或家庭共享范围并检索后，编辑主要命中的记忆。"));
    m_edit->setEnabled(false);
    row->addWidget(m_edit);
    auto *editor = new MemoryEditDialog(this);
    connect(m_edit, &QPushButton::clicked, this, [this, editor]() {
        if (!m_knowledge.isEmpty() && !m_scope->currentData().toString().isEmpty())
            editor->openMemory(m_knowledge, m_scope->currentData().toString());
    });
    connect(editor, &MemoryEditDialog::memoryUpdated, this, [this]() {
        clearResult();
        m_status->setText(tr("记忆已更新，请重新检索查看当前结果。"));
    });
    connect(write, &QPushButton::clicked, writeDialog, &QDialog::show);
    connect(writeDialog, &MemoryWriteDialog::memoryAccepted, m_audit,
            [this](const QString &id) { m_audit->setEvidenceIds({id}); });
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
    m_showRaw = new QCheckBox(tr("查看原始数据（高级）"), this);
    m_showRaw->setObjectName("memoryEvidenceRaw");
    m_showRaw->setEnabled(false);
    layout->addWidget(m_showRaw);
    m_detail = new QPlainTextEdit(this);
    m_detail->setObjectName(QStringLiteral("memoryEvidence"));
    m_detail->setReadOnly(true);
    m_detail->setAccessibleName(tr("原始证据正文"));
    layout->addWidget(m_detail, 2);
    connect(m_showRaw, &QCheckBox::toggled, this, [this](bool checked) {
        m_detail->setPlainText(checked ? m_evidenceRaw : m_evidenceText);
    });
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
        m_knowledge = result.value("source_knowledge").toString();
        m_edit->setEnabled(!m_knowledge.isEmpty() && !m_scope->currentData().toString().isEmpty());
        const QString answer = result.value(QStringLiteral("answer")).toString();
        m_answer->setPlainText(answer);
        m_status->setText(answer.isEmpty() ? tr("没有找到匹配的记忆。") : tr("检索完成，选择来源查看证据。"));
        for (const auto &value : result.value(QStringLiteral("source_evidence")).toArray()) {
            const QString source = value.toString();
            if (source.isEmpty()) continue;
            auto *item = new QListWidgetItem(tr("查看来源 %1").arg(m_sources->count() + 1), m_sources);
            item->setData(Qt::UserRole, source);
        }
        QStringList ids;
        for (int i = 0; i < m_sources->count(); ++i) ids << m_sources->item(i)->data(Qt::UserRole).toString();
        m_audit->setEvidenceIds(ids);
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
        m_expectedEvidenceScope = item->data(Qt::UserRole + 1).toString();
        clearEvidence();
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
        if (m_evidence.isEmpty()) {
            m_detailMeta->clear(); // invalidated while the uncorrelated read was pending
            return;
        }
        if (evidence.value(QStringLiteral("id")).toString() != m_evidence) {
            m_detailMeta->setText(tr("证据响应与所选来源不一致，请重新选择来源。"));
            m_sources->setCurrentRow(-1);
            return;
        }
        if (!m_expectedEvidenceScope.isEmpty() &&
            (evidence.value("scope").toString() != m_expectedEvidenceScope ||
             !evidence.value("sensitivity").isDouble() ||
             evidence.value("sensitivity").toDouble() != 0)) {
            m_detailMeta->setText(tr("此会话来源的范围或敏感级别已变化，不能按会话引用展示。"));
            m_sources->setCurrentRow(-1);
            return;
        }
        const QJsonObject raw = evidence.value(QStringLiteral("raw")).toObject();
        m_detailMeta->setText(tr("%1\n来源：%2 · 范围：%3 · 质量：%4")
            .arg(raw.value(QStringLiteral("title")).toString(tr("原始证据")),
                 evidence.value(QStringLiteral("source_type")).toString(),
                 evidence.value(QStringLiteral("scope")).toString())
            .arg(evidence.value(QStringLiteral("quality_score")).toDouble(), 0, 'f', 2));
        m_evidenceText = readableEvidence(raw);
        m_evidenceRaw = QString::fromUtf8(QJsonDocument(raw).toJson(QJsonDocument::Indented));
        m_showRaw->setEnabled(!raw.isEmpty());
        m_detail->setPlainText(m_evidenceText);
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

bool MemoryWorkspace::showAgentSources(const AgentEvidenceResult &result, const QString &scope)
{
    if (hasPendingOperation() || result.status != AgentEvidenceResult::Ready ||
        result.references.size() > 256 || scope.isEmpty() || m_scope->findData(scope) < 0)
        return false;
    const QRegularExpression validId(QStringLiteral("\\Aevd_[A-Za-z0-9_-]{8,128}\\z"));
    for (const auto &source : result.references) {
        if (source.scope != scope || !validId.match(source.evidenceId).hasMatch()) return false;
    }
    m_scope->setCurrentIndex(m_scope->findData(scope));
    clearResult();
    m_query->clear();
    m_agentSources = true;
    m_answer->hide();
    m_tabs->setCurrentIndex(0);
    m_status->setText(result.references.isEmpty()
        ? tr("会话记录中没有可核验的记忆来源；这不代表会话未使用记忆。")
        : tr("本会话记忆来源：选择后读取当前证据。此列表不是每条回答的逐句引用。"));
    QSet<QString> seen;
    QStringList ids;
    for (const auto &source : result.references) {
        if (seen.contains(source.evidenceId)) continue;
        seen.insert(source.evidenceId);
        auto *item = new QListWidgetItem(source.title.isEmpty()
            ? tr("查看来源 %1").arg(m_sources->count() + 1) : source.title.left(512), m_sources);
        item->setData(Qt::UserRole, source.evidenceId);
        item->setData(Qt::UserRole + 1, scope);
        ids << source.evidenceId;
    }
    m_audit->setEvidenceIds(ids);
    return true;
}

void MemoryWorkspace::clearAgentSources()
{
    if (!m_agentSources) return;
    clearResult();
    m_status->setText(tr("会话或 Runtime 已切换，请重新读取本会话来源。"));
}

void MemoryWorkspace::clearEvidence()
{
    m_evidenceText.clear();
    m_evidenceRaw.clear();
    m_showRaw->setChecked(false);
    m_showRaw->setEnabled(false);
    m_detail->clear();
}

void MemoryWorkspace::notifyDataChanged()
{
    if (!m_request && !m_evidenceBusy && m_sources->count() == 0 && m_knowledge.isEmpty()
        && m_answer->toPlainText().isEmpty()) return;
    clearResult();
    m_status->setText(tr("记忆数据已变化或连接恢复，旧结果已清除。请重新检索或读取会话来源；编辑草稿不会被覆盖。"));
}

void MemoryWorkspace::clearResult()
{
    m_agentSources = false;
    m_answer->show();
    m_knowledge.clear();
    m_edit->setEnabled(false);
    m_request = 0;
    m_evidence.clear();
    m_audit->setEvidenceIds({});
    m_answer->clear();
    m_sources->clear();
    clearEvidence();
    m_detailMeta->clear();
    m_search->setEnabled(!m_evidenceBusy);
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
