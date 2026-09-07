#include "MemoryEditDialog.h"
#include "services/HttpBackendTransport.h"
#include <QFormLayout>
#include <QCheckBox>
#include <QHBoxLayout>
#include <QJsonDocument>
#include <QLabel>
#include <QLineEdit>
#include <QMessageBox>
#include <QPlainTextEdit>
#include <QPushButton>
#include <QSignalBlocker>
#include <QUuid>
#include <QVBoxLayout>

namespace pixiu {
MemoryEditDialog::MemoryEditDialog(QWidget *parent, BackendTransport *transport)
    : QDialog(parent), m_transport(transport ? transport : new HttpBackendTransport(this))
{
    setWindowTitle(tr("编辑记忆"));
    setWindowModality(Qt::WindowModal);
    resize(640, 520);
    auto *layout = new QVBoxLayout(this);
    m_target = new QLabel(this);
    m_target->setTextFormat(Qt::PlainText);
    m_target->setWordWrap(true);
    layout->addWidget(m_target);
    m_title = new QLineEdit(this);
    m_title->setObjectName("editTitle");
    m_title->setMaxLength(512);
    m_body = new QPlainTextEdit(this);
    m_body->setObjectName("editBody");
    auto *form = new QFormLayout;
    form->addRow(tr("标题"), m_title);
    m_bodyLabel = new QLabel(tr("正文"), this);
    m_bodyLabel->setBuddy(m_body);
    form->addRow(m_bodyLabel, m_body);
    layout->addLayout(form, 1);
    m_structured = new QCheckBox(tr("高级：编辑完整结构（JSON）"), this);
    m_structured->setObjectName("editStructured");
    layout->addWidget(m_structured);
    m_status = new QLabel(tr("请选择明确范围内的检索结果。"), this);
    m_status->setObjectName("editStatus");
    m_status->setTextFormat(Qt::PlainText);
    m_status->setWordWrap(true);
    layout->addWidget(m_status);
    m_reload = new QPushButton(tr("重新读取"), this);
    m_reload->setObjectName("editReload");
    m_save = new QPushButton(tr("保存修改"), this);
    m_save->setObjectName("editSave");
    m_save->setAutoDefault(false);
    m_close = new QPushButton(tr("关闭"), this);
    m_close->setDefault(true);
    auto *buttons = new QHBoxLayout;
    buttons->addWidget(m_reload);
    buttons->addStretch();
    buttons->addWidget(m_close);
    buttons->addWidget(m_save);
    layout->addLayout(buttons);
    connect(m_close, &QPushButton::clicked, this, &MemoryEditDialog::reject);
    connect(m_save, &QPushButton::clicked, this, &MemoryEditDialog::submit);
    connect(m_title, &QLineEdit::textChanged, this, &MemoryEditDialog::updateControls);
    connect(m_body, &QPlainTextEdit::textChanged, this, &MemoryEditDialog::updateControls);
    connect(m_structured, &QCheckBox::toggled, this, [this](bool structured) {
        bool valid = false;
        const auto body = editedBody(&valid);
        if (!valid || (!structured && !body.value("text").isString())) {
            const QSignalBlocker blocker(m_structured);
            m_structured->setChecked(!m_textMode);
            m_status->setText(tr("请先填写有效 JSON 对象，且保留字符串 text 字段，才能切换回文本模式。"));
            return;
        }
        m_draftBody = body;
        m_textMode = !structured;
        m_bodyLabel->setText(m_textMode ? tr("正文") : tr("完整正文（JSON 对象）"));
        m_body->setPlainText(m_textMode ? body.value("text").toString()
            : QString::fromUtf8(QJsonDocument(body).toJson(QJsonDocument::Indented)));
        updateControls();
    });
    connect(m_reload, &QPushButton::clicked, this, [this]() {
        if (m_pending != Pending::None) return;
        if (hasChanges()) {
            if (QMessageBox::question(this, tr("重新读取记忆"),
                tr("重新读取会替换当前编辑内容。请先复制需要保留的修改，是否继续？"),
                QMessageBox::Yes | QMessageBox::No, QMessageBox::No) != QMessageBox::Yes) return;
        }
        refresh();
    });
    connect(m_transport, &BackendTransport::memoryItemResult, this, [this](const QJsonObject &result) {
        if (m_pending != Pending::Read) return;
        m_pending = Pending::None;
        const int version = result.value("version").toInt();
        if (result.value("knowledge_id").toString() != m_id || result.value("scope").toString() != m_scope
            || version < 1 || result.value("version").toDouble() != version
            || !result.value("body").isObject() || !result.value("title").isString()
            || result.value("title").toString().size() > m_title->maxLength()) {
            m_status->setText(tr("响应缺少完整内容或与目标不符，禁止保存，请重新读取。"));
            updateControls();
            return;
        }
        m_original = result;
        m_draftBody = result.value("body").toObject();
        m_version = version;
        m_stale = false;
        m_textMode = m_draftBody.value("text").isString();
        {
            const QSignalBlocker blocker(m_structured);
            m_structured->setChecked(!m_textMode);
        }
        m_structured->setVisible(m_textMode);
        m_bodyLabel->setText(m_textMode ? tr("正文") : tr("完整正文（JSON 对象）"));
        m_title->setText(result.value("title").toString());
        m_body->setPlainText(m_textMode ? m_draftBody.value("text").toString()
            : QString::fromUtf8(QJsonDocument(m_draftBody).toJson(QJsonDocument::Indented)));
        m_target->setText(tr("%1\n范围：%2 · 版本：%3").arg(m_id, m_scope).arg(version));
        m_status->setText(m_textMode
            ? tr("直接修改正文即可，其他字段会保留。保存不会改变记忆范围；同步送达需单独核对。")
            : tr("此记忆包含结构化内容，请保留需要的字段并填写有效 JSON 对象。保存不会改变记忆范围。"));
        updateControls();
    });
    connect(m_transport, &BackendTransport::memoryUpdated, this, [this](const QJsonObject &result) {
        if (m_pending != Pending::Save) return;
        m_pending = Pending::None;
        if (result.value("knowledge_id").toString() != m_id || result.value("status").toString() != "updated"
            || result.value("version").toDouble() != m_version + 1 || result.value("evidence_id").toString().isEmpty()) {
            m_status->setText(tr("无法确认保存结果。输入已保留，原样重试会使用同一请求标识。"));
            updateControls();
            return;
        }
        m_original.insert("title", m_title->text().trimmed());
        m_original.insert("body", editedBody());
        m_version = 0;
        m_status->setText(tr("修改已保存。继续编辑前请重新读取最新版本。"));
        updateControls();
        emit memoryUpdated();
    });
    connect(m_transport, &BackendTransport::errorOccurred, this,
        [this](const QString &code, const QString &message, const QString &) {
        if (m_pending == Pending::None) return;
        const bool saving = m_pending == Pending::Save;
        m_pending = Pending::None;
        if (saving && (code == "VERSION_CONFLICT" || code == "KNOWLEDGE_NOT_ACTIVE"
            || code == "NOT_FOUND" || code == "IDEMPOTENCY_FAILED" || code == "IDEMPOTENCY_CONFLICT")) m_stale = true;
        m_status->setText(m_stale
            ? tr("保存已被阻止（%1）：%2。输入已保留，请先复制修改并重新读取。失败收据可能需要人工核验恢复，不能自动重放。").arg(code, message)
            : tr("操作失败（%1）：%2。输入已保留，可重试。").arg(code, message));
        updateControls();
    });
    updateControls();
}
void MemoryEditDialog::openMemory(const QString &id, const QString &scope)
{
    if (m_pending != Pending::None || id.isEmpty() || scope.isEmpty()) return;
    if (isVisible()) { raise(); activateWindow(); return; }
    m_id = id;
    m_scope = scope;
    m_original = {};
    m_draftBody = {};
    m_title->clear();
    m_body->clear();
    show();
    refresh();
}
void MemoryEditDialog::refresh()
{
    if (m_pending != Pending::None || m_id.isEmpty()) return;
    m_version = 0;
    m_key.clear();
    m_lastPayload = {};
    m_pending = Pending::Read;
    m_target->setText(tr("%1\n范围：%2").arg(m_id, m_scope));
    m_status->setText(tr("正在读取完整记忆…"));
    updateControls();
    m_transport->memoryItem(m_id, m_scope);
}
void MemoryEditDialog::updateControls()
{
    const bool idle = m_pending == Pending::None;
    m_title->setEnabled(idle && m_version > 0);
    m_body->setReadOnly(!idle || m_version == 0);
    m_reload->setEnabled(idle && !m_id.isEmpty());
    m_close->setEnabled(idle);
    m_structured->setEnabled(idle && m_version > 0);
    bool valid = false;
    editedBody(&valid);
    m_save->setEnabled(idle && m_version > 0 && !m_stale && hasChanges()
        && !m_title->text().trimmed().isEmpty() && valid);
}
QJsonObject MemoryEditDialog::editedBody(bool *valid) const
{
    if (m_textMode) {
        auto body = m_draftBody;
        body.insert("text", m_body->toPlainText());
        if (valid) *valid = true;
        return body;
    }
    const auto document = QJsonDocument::fromJson(m_body->toPlainText().toUtf8());
    if (valid) *valid = document.isObject();
    return document.object();
}
bool MemoryEditDialog::hasChanges() const
{
    if (m_original.isEmpty()) return false;
    bool valid = false;
    const auto body = editedBody(&valid);
    return !valid || m_title->text().trimmed() != m_original.value("title").toString()
        || body != m_original.value("body").toObject();
}
void MemoryEditDialog::submit()
{
    if (!m_save->isEnabled() || m_pending != Pending::None) return;
    QJsonObject payload{{"knowledge_id", m_id}, {"scope", m_scope}, {"expected_version", m_version}};
    const auto body = editedBody();
    if (m_title->text().trimmed() != m_original.value("title").toString())
        payload.insert("title", m_title->text().trimmed());
    if (body != m_original.value("body").toObject()) payload.insert("body", body);
    if (payload != m_lastPayload || m_key.isEmpty()) {
        m_lastPayload = payload;
        m_key = QUuid::createUuid().toString(QUuid::WithoutBraces);
    }
    payload.insert("idempotency_key", m_key);
    m_pending = Pending::Save;
    m_status->setText(tr("正在保存修改…"));
    updateControls();
    m_transport->updateMemory(payload);
}
void MemoryEditDialog::reject()
{
    if (m_pending != Pending::None) return;
    if (hasChanges() && QMessageBox::question(this, tr("关闭编辑"),
        tr("有尚未确认保存的修改。是否放弃这些修改并关闭？"),
        QMessageBox::Yes | QMessageBox::No, QMessageBox::No) != QMessageBox::Yes) return;
    QDialog::reject();
}
}
