#include "MemoryEditDialog.h"
#include "services/HttpBackendTransport.h"
#include <QFormLayout>
#include <QHBoxLayout>
#include <QJsonDocument>
#include <QLabel>
#include <QLineEdit>
#include <QMessageBox>
#include <QPlainTextEdit>
#include <QPushButton>
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
    form->addRow(tr("完整正文（JSON 对象）"), m_body);
    layout->addLayout(form, 1);
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
    connect(m_reload, &QPushButton::clicked, this, [this]() {
        if (m_pending != Pending::None) return;
        if (!m_title->text().isEmpty() || !m_body->toPlainText().isEmpty()) {
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
        m_version = version;
        m_stale = false;
        m_title->setText(result.value("title").toString());
        m_body->setPlainText(QString::fromUtf8(QJsonDocument(result.value("body").toObject()).toJson(QJsonDocument::Indented)));
        m_target->setText(tr("%1\n范围：%2 · 版本：%3").arg(m_id, m_scope).arg(version));
        m_status->setText(tr("修改完整正文时请保留需要的字段。保存不会改变记忆范围；其他设备的同步结果需单独核对。"));
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
    const auto body = QJsonDocument::fromJson(m_body->toPlainText().toUtf8());
    const bool changed = m_title->text().trimmed() != m_original.value("title").toString()
        || body.object() != m_original.value("body").toObject();
    m_save->setEnabled(idle && m_version > 0 && !m_stale && changed
        && !m_title->text().trimmed().isEmpty() && body.isObject());
}
void MemoryEditDialog::submit()
{
    if (!m_save->isEnabled() || m_pending != Pending::None) return;
    QJsonObject payload{{"knowledge_id", m_id}, {"scope", m_scope}, {"expected_version", m_version}};
    const auto body = QJsonDocument::fromJson(m_body->toPlainText().toUtf8()).object();
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
    if (m_pending == Pending::None) QDialog::reject();
}
}
