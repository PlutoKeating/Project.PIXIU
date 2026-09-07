#include "MemoryWriteDialog.h"
#include "MemoryScopes.h"
#include "services/HttpBackendTransport.h"
#include <QComboBox>
#include <QFormLayout>
#include <QHBoxLayout>
#include <QLabel>
#include <QLineEdit>
#include <QPlainTextEdit>
#include <QPushButton>
#include <QUuid>
#include <QVBoxLayout>

namespace pixiu {
MemoryWriteDialog::MemoryWriteDialog(QWidget *parent, BackendTransport *transport)
    : QDialog(parent), m_transport(transport ? transport : new HttpBackendTransport(this))
{
    setWindowTitle(tr("录入记忆"));
    resize(560, 440);
    m_title = new QLineEdit(this);
    m_title->setObjectName(QStringLiteral("writeTitle"));
    m_body = new QPlainTextEdit(this);
    m_body->setObjectName(QStringLiteral("writeBody"));
    m_scope = new QComboBox(this);
    m_scope->setObjectName(QStringLiteral("writeScope"));
    populateMemoryScopes(m_scope, false, true);
    auto *form = new QFormLayout;
    form->addRow(tr("标题"), m_title);
    form->addRow(tr("正文"), m_body);
    form->addRow(tr("范围"), m_scope);
    auto *privacy = new QLabel(tr("个人记忆默认不共享。共享范围的敏感内容会被后端拒绝；本界面不会自动改为共享。"), this);
    privacy->setWordWrap(true);
    m_status = new QLabel(this);
    m_status->setObjectName(QStringLiteral("writeStatus"));
    m_status->setTextFormat(Qt::PlainText);
    m_status->setWordWrap(true);
    m_save = new QPushButton(tr("保存记忆"), this);
    m_save->setObjectName(QStringLiteral("writeSave"));
    m_cancel = new QPushButton(tr("关闭"), this);
    m_cancel->setDefault(true);
    m_save->setAutoDefault(false);
    auto *buttons = new QHBoxLayout;
    buttons->addStretch();
    buttons->addWidget(m_cancel);
    buttons->addWidget(m_save);
    auto *layout = new QVBoxLayout(this);
    layout->addLayout(form);
    layout->addWidget(privacy);
    layout->addWidget(m_status);
    layout->addLayout(buttons);
    connect(m_title, &QLineEdit::textChanged, this, &MemoryWriteDialog::updateForm);
    connect(m_body, &QPlainTextEdit::textChanged, this, &MemoryWriteDialog::updateForm);
    connect(m_cancel, &QPushButton::clicked, this, &MemoryWriteDialog::reject);
    connect(m_save, &QPushButton::clicked, this, &MemoryWriteDialog::submit);
    connect(m_transport, &BackendTransport::writeAcknowledged, this, [this](const QJsonObject &result) {
        if (!m_busy) return;
        m_busy = false;
        const QString evidence = result.value(QStringLiteral("evidence_id")).toString();
        if (result.value(QStringLiteral("status")).toString() != QStringLiteral("accepted") || evidence.isEmpty()) {
            m_status->setText(tr("无法确认写入结果，输入已保留。重试将使用同一请求标识。"));
            updateForm();
            return;
        }
        m_status->setText(tr("后端已接收记忆。可返回检索查看结果；共享是否送达请以同步状态为准。"));
        m_title->clear();
        m_body->clear();
        m_lastPayload = {};
        m_idempotencyKey.clear();
        updateForm();
        emit memoryAccepted(evidence);
    });
    connect(m_transport, &BackendTransport::errorOccurred, this,
            [this](const QString &code, const QString &message, const QString &) {
        if (!m_busy) return;
        m_busy = false;
        m_status->setText(tr("保存失败（%1）：%2。输入已保留，可重试。").arg(code, message));
        updateForm();
    });
    updateForm();
}
void MemoryWriteDialog::updateForm()
{
    m_title->setEnabled(!m_busy);
    m_body->setEnabled(!m_busy);
    m_scope->setEnabled(!m_busy);
    m_cancel->setEnabled(!m_busy);
    m_save->setEnabled(!m_busy && !m_title->text().trimmed().isEmpty() && !m_body->toPlainText().trimmed().isEmpty());
}
void MemoryWriteDialog::submit()
{
    if (!m_save->isEnabled() || m_busy) return;
    QJsonObject payload{{QStringLiteral("source_type"), QStringLiteral("MANUAL_CONFIG")},
        {QStringLiteral("scope"), m_scope->currentData().toString()},
        {QStringLiteral("raw"), QJsonObject{{QStringLiteral("title"), m_title->text().trimmed()},
            {QStringLiteral("body"), QJsonObject{{QStringLiteral("text"), m_body->toPlainText().trimmed()}}}}}};
    if (payload != m_lastPayload || m_idempotencyKey.isEmpty()) {
        m_lastPayload = payload;
        m_idempotencyKey = QUuid::createUuid().toString(QUuid::WithoutBraces);
    }
    payload.insert(QStringLiteral("idempotency_key"), m_idempotencyKey);
    m_busy = true;
    m_status->setText(tr("正在保存，请勿重复提交…"));
    updateForm();
    m_transport->writeMemory(payload);
}
void MemoryWriteDialog::reject()
{
    if (!m_busy) QDialog::reject();
}
}
