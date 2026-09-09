#include "MemoryWorkspace.h"
#include "MemoryScopes.h"
#include "MemoryScopeControl.h"
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
#include <QSplitter>
#include <QSet>
#include <QRegularExpression>
#include <QDateTime>
#include <QMessageBox>
#include <QScrollArea>
#include <QPixmap>
#include <cmath>
#include <functional>

namespace pixiu {
namespace {
QString captureDetails(const QJsonObject &evidence, bool &valid)
{
    valid = false;
    const auto value = evidence.value("capture_source");
    if (value.isUndefined() || value.isNull())
        return MemoryWorkspace::tr("文件采集来源：未记录。不能根据文件名推断原始路径。");
    const auto source = value.toObject();
    const QString path = source.value("path").toString();
    const QString method = source.value("method").toString();
    const double seconds = source.value("captured_at").toDouble(-1);
    const QRegularExpression privateScope(QStringLiteral("\\Auser:[A-Za-z0-9._-]+\\z"));
    const QString type = evidence.value("source_type").toString();
    if (!value.isObject() || source.size() != 4 || source.value("kind") != "directory"
        || (method != "text" && method != "ocr")
        || !path.startsWith('/') || path.size() < 2 || path.size() > 8192
        || path.toUcs4().size() > 4096 || path.contains(QChar(0))
        || !source.value("captured_at").isDouble() || !std::isfinite(seconds)
        || seconds < 0 || seconds > 253402300799.0 || std::floor(seconds) != seconds
        || !privateScope.match(evidence.value("scope").toString()).hasMatch()
        || (type != "MANUAL_CONFIG" && type != "OCR"))
        return MemoryWorkspace::tr("文件采集来源数据无效，未展示路径；正文仍可阅读。");
    // JSON quoting keeps newlines and quotes in filenames distinct from UI labels.
    valid = true;
    const QString quoted = QString::fromUtf8(QJsonDocument(QJsonArray{path}).toJson(QJsonDocument::Compact));
    return MemoryWorkspace::tr("文件采集方式：%1\n采集时路径：%2\n采集记录时间（UTC）：%3\n仅记录采集时来源，不保证原文件仍存在或内容未变化。")
        .arg(method == "text" ? MemoryWorkspace::tr("文本读取") : MemoryWorkspace::tr("图片 OCR"),
             quoted.mid(1, quoted.size() - 2),
             QDateTime::fromSecsSinceEpoch(static_cast<qint64>(seconds), Qt::UTC).toString(Qt::ISODate));
}

QString readableEvidence(const QJsonObject &raw)
{
    QJsonObject fields = raw;
    fields.remove("original_image");
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
    auto *stages = new QWidget(tabs);
    auto *stageLayout = new QVBoxLayout(stages);
    auto *stageNotice = new QLabel(tr("当前轮次保存为短期上下文；会话压缩和切换保存为阶段记录。选择值得复用的内容，确认后保存为长期记忆。完整对话与显式记忆仍按现有规则留存。"), stages);
    stageNotice->setWordWrap(true);
    stageLayout->addWidget(stageNotice);
    auto *stageScope = new QComboBox(stages);
    populateMemoryScopes(stageScope, false, true);
    stageLayout->addWidget(new MemoryScopeControl(stageScope));
    auto *stageRefresh = new QPushButton(tr("读取短期与阶段记忆"), stages);
    stageLayout->addWidget(stageRefresh);
    auto *stageItems = new QListWidget(stages);
    stageItems->setObjectName("memoryStageItems");
    stageLayout->addWidget(stageItems, 1);
    auto *stageDetails = new QPlainTextEdit(stages);
    stageDetails->setReadOnly(true);
    stageLayout->addWidget(stageDetails, 1);
    auto *keepStage = new QPushButton(tr("将所选内容保存为长期记忆"), stages);
    stageLayout->addWidget(keepStage);
    auto *stageHttp = new HttpBackendTransport(stages);
    connect(stageRefresh, &QPushButton::clicked, stages, [=]() {
        stageHttp->flowContexts(stageScope->currentData().toString());
    });
    connect(stageHttp, &HttpBackendTransport::flowContextsResult, stages, [=](const QJsonObject &result) {
        stageItems->clear(); stageDetails->clear();
        for (const auto &value : result.value("contexts").toArray()) {
            auto entry = value.toObject();
            const auto payload = entry.value("payload").toObject();
            const auto data = payload.value("data").toObject();
            QString text = data.value("summary").toString();
            if (text.isEmpty()) text = data.value("message").toString();
            if (text.isEmpty()) text = data.value("assistant").toString();
            if (text.isEmpty()) text = QString::fromUtf8(QJsonDocument(payload).toJson(QJsonDocument::Indented));
            entry.insert("display_text", text);
            auto *row = new QListWidgetItem((entry.value("tier") == "SHORT_TERM" ? tr("短期 · ") : tr("阶段 · "))
                + text.left(100), stageItems);
            row->setData(Qt::UserRole, entry);
        }
    });
    connect(stageItems, &QListWidget::currentItemChanged, stages, [=](QListWidgetItem *row) {
        stageDetails->setPlainText(row ? row->data(Qt::UserRole).toJsonObject().value("display_text").toString() : QString());
    });
    connect(keepStage, &QPushButton::clicked, stages, [=]() {
        auto *row = stageItems->currentItem();
        if (!row || QMessageBox::question(stages, tr("保留阶段记忆"), tr("将已查看的内容保存为长期记忆？")) != QMessageBox::Yes) return;
        const auto entry = row->data(Qt::UserRole).toJsonObject();
        keepStage->setEnabled(false);
        stageHttp->promoteMemory({{"source", entry.value("tier")}, {"scope", entry.value("scope")},
            {"context_ids", QJsonArray{entry.value("id")}}});
    });
    connect(stageHttp, &BackendTransport::promoteResult, stages, [=](const QJsonObject &) {
        keepStage->setEnabled(true); stageDetails->setPlainText(tr("已保存为长期记忆，可以跨会话检索。"));
        stageHttp->flowContexts(stageScope->currentData().toString());
    });
    connect(stageHttp, &BackendTransport::errorOccurred, stages, [=](const QString &, const QString &, const QString &) {
        keepStage->setEnabled(true); stageDetails->setPlainText(tr("操作未完成，请检查连接或刷新后重试。"));
    });
    tabs->addTab(stages, tr("短期与阶段记忆"));
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
    row->addWidget(new MemoryScopeControl(m_scope));
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
    auto *reader = new QSplitter(Qt::Horizontal, queryPage);
    reader->setObjectName(QStringLiteral("memoryReaderSplit"));
    reader->setChildrenCollapsible(false);
    auto *results = new QWidget(reader);
    results->setMinimumWidth(200);
    auto *resultLayout = new QVBoxLayout(results);
    resultLayout->setContentsMargins(0, 0, 0, 0);
    auto *evidencePane = new QWidget(reader);
    evidencePane->setMinimumWidth(400);
    auto *evidenceLayout = new QVBoxLayout(evidencePane);
    evidenceLayout->setContentsMargins(0, 0, 0, 0);
    reader->setStretchFactor(0, 1);
    reader->setStretchFactor(1, 2);
    reader->setSizes({360, 760});
    layout->addWidget(reader, 1);
    m_answer = new QPlainTextEdit(this);
    m_answer->setObjectName(QStringLiteral("memoryAnswer"));
    m_answer->setReadOnly(true);
    m_answer->setAccessibleName(tr("记忆检索结果"));
    resultLayout->addWidget(m_answer, 1);
    m_sources = new QListWidget(this);
    m_sources->setObjectName(QStringLiteral("memorySources"));
    m_sources->setAccessibleName(tr("结果来源，选择以阅读证据"));
    resultLayout->addWidget(m_sources, 2);
    m_detailMeta = new QLabel(this);
    m_detailMeta->setWordWrap(true);
    m_detailMeta->setTextFormat(Qt::PlainText);
    evidenceLayout->addWidget(m_detailMeta);
    m_originalImage = new QPushButton(tr("查看账单原图"), this);
    m_originalImage->setObjectName("viewOriginalBillImage");
    m_originalImage->hide();
    evidenceLayout->addWidget(m_originalImage);
    connect(m_originalImage, &QPushButton::clicked, this, [this] {
        QPixmap picture;
        if (!picture.loadFromData(m_originalImage->property("data").toByteArray())) return;
        QDialog dialog(this); dialog.setWindowTitle(tr("账单原图")); dialog.resize(800, 600);
        auto *layout = new QVBoxLayout(&dialog);
        auto *scroll = new QScrollArea(&dialog); auto *label = new QLabel;
        label->setPixmap(picture); scroll->setWidget(label); layout->addWidget(scroll);
        dialog.exec();
    });
    m_captureStatus = new QLabel(this);
    m_captureStatus->setObjectName(QStringLiteral("memoryCaptureStatus"));
    m_captureStatus->setTextFormat(Qt::PlainText);
    m_captureStatus->setWordWrap(true);
    m_captureStatus->setTextInteractionFlags(Qt::TextSelectableByMouse | Qt::TextSelectableByKeyboard);
    m_captureStatus->setSizePolicy(QSizePolicy::Preferred, QSizePolicy::Maximum);
    m_captureStatus->hide();
    evidenceLayout->addWidget(m_captureStatus);
    m_captureDetails = new QPlainTextEdit(this);
    m_captureDetails->setObjectName(QStringLiteral("memoryCaptureSource"));
    m_captureDetails->setAccessibleName(tr("文件采集来源，只读"));
    m_captureDetails->setReadOnly(true);
    m_captureDetails->setMaximumHeight(110);
    m_captureDetails->hide();
    evidenceLayout->addWidget(m_captureDetails);
    m_showRaw = new QCheckBox(tr("查看原始数据（高级）"), this);
    m_showRaw->setObjectName("memoryEvidenceRaw");
    m_showRaw->setEnabled(false);
    evidenceLayout->addWidget(m_showRaw);
    m_detail = new QPlainTextEdit(this);
    m_detail->setObjectName(QStringLiteral("memoryEvidence"));
    m_detail->setReadOnly(true);
    m_detail->setAccessibleName(tr("原始证据正文"));
    m_detail->setMinimumHeight(100);
    evidenceLayout->addWidget(m_detail, 1);
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
        const auto original = raw.value("original_image").toObject();
        const QByteArray imageData = QByteArray::fromBase64(original.value("base64").toString().toLatin1());
        m_originalImage->setProperty("data", imageData);
        m_originalImage->setVisible(!imageData.isEmpty());
        m_evidenceText = readableEvidence(raw);
        bool validCapture = false;
        const QString captureText = captureDetails(evidence, validCapture);
        m_captureDetails->setPlainText(validCapture ? captureText : QString());
        m_captureDetails->setVisible(validCapture);
        m_captureStatus->setText(validCapture ? QString() : captureText);
        m_captureStatus->setVisible(!validCapture);
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
        if ((source.scope != scope && !result.readScopes.contains(source.scope)) || !validId.match(source.evidenceId).hasMatch()) return false;
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
        item->setData(Qt::UserRole + 1, source.scope);
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
    m_originalImage->hide();
    m_originalImage->setProperty("data", QByteArray());
    m_captureStatus->clear();
    m_captureStatus->hide();
    m_captureDetails->clear();
    m_captureDetails->hide();
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
