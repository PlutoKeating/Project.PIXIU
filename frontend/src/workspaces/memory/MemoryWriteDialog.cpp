#include "MemoryWriteDialog.h"
#include "MemoryScopes.h"
#include "MemoryScopeControl.h"
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
#include <QFileDialog>
#include <QFile>
#include <QFileInfo>
#include <QImage>
#include <QTableWidget>
#include <QHeaderView>
#include <QJsonArray>
#include <QDate>
#include <cmath>

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
    m_image = new QPushButton(tr("选择图片账单并识别（PNG/JPEG，≤2 MB）"), this);
    m_image->setObjectName("importBillImage");
    m_items = new QTableWidget(0, 4, this);
    m_items->setObjectName("billItems");
    m_items->setHorizontalHeaderLabels({tr("日期 YYYY-MM-DD"), tr("类别"), tr("项目/商家"), tr("金额（元）")});
    m_items->horizontalHeader()->setSectionResizeMode(QHeaderView::Stretch);
    m_items->hide();
    auto *addItem = new QPushButton(tr("添加账单明细"), this);
    auto *removeItem = new QPushButton(tr("删除所选明细"), this);
    connect(addItem, &QPushButton::clicked, this, [this] {
        if (m_busy || m_ocrBusy) return;
        m_items->show(); m_items->insertRow(m_items->rowCount()); updateForm();
    });
    connect(removeItem, &QPushButton::clicked, this, [this] {
        if (!m_busy && !m_ocrBusy && m_items->currentRow() >= 0) m_items->removeRow(m_items->currentRow());
        updateForm();
    });
    auto *ocr = new HttpBackendTransport(this);
    connect(m_image, &QPushButton::clicked, this, [this, ocr] {
        const QString path = QFileDialog::getOpenFileName(this, tr("选择账单图片"), {}, tr("图片 (*.png *.jpg *.jpeg)"));
        if (path.isEmpty()) return;
        QFile file(path);
        if (!file.open(QIODevice::ReadOnly) || file.size() > 2*1024*1024) {
            m_status->setText(tr("无法读取图片，或图片超过 2 MB。请换一张图片。")); return;
        }
        const auto data = file.readAll();
        if (QImage::fromData(data).isNull()) { m_status->setText(tr("图片无法解码，请选择 PNG 或 JPEG。")); return; }
        m_originalImage = {{"base64", QString::fromLatin1(data.toBase64())}, {"name", QFileInfo(path).fileName()}};
        m_title->setText(QFileInfo(path).completeBaseName());
        m_body->clear(); m_items->setRowCount(0); m_items->show();
        m_ocrBusy = true; updateForm();
        m_status->setText(tr("正在识别。完成后请核对日期、类别和金额，再保存。"));
        ocr->recognizeImage({{"image_base64", m_originalImage.value("base64")}});
    });
    connect(ocr, &HttpBackendTransport::imageRecognized, this, [this](const QJsonObject &result) {
        m_ocrBusy = false;
        m_body->setPlainText(result.value("text").toString());
        const auto items = result.value("items").toArray();
        m_items->setRowCount(items.size());
        const QStringList keys{"date", "category", "vendor", "amount"};
        for (int row = 0; row < items.size(); ++row)
            for (int col = 0; col < keys.size(); ++col) {
                const auto value = items[row].toObject().value(keys[col]);
                m_items->setItem(row, col, new QTableWidgetItem(value.isDouble() ? QString::number(value.toDouble(), 'f', 2) : value.toString()));
            }
        m_status->setText(tr("识别结果尚未保存。请核对正文和明细；可补充漏识别项目，确认后点击保存。"));
        updateForm();
    });
    connect(ocr, &BackendTransport::errorOccurred, this, [this](const QString &, const QString &, const QString &) {
        if (!m_ocrBusy) return;
        m_ocrBusy = false; updateForm();
        m_status->setText(tr("图片识别未完成，请检查麒麟 OCR 服务。也可手动填写正文及明细后保存，原图会保留。"));
    });
    auto *form = new QFormLayout;
    form->addRow(tr("标题"), m_title);
    form->addRow(tr("正文"), m_body);
    form->addRow(tr("范围"), new MemoryScopeControl(m_scope));
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
    layout->addWidget(m_image);
    layout->addLayout(form);
    layout->addWidget(m_items);
    auto *itemActions = new QHBoxLayout; itemActions->addWidget(addItem); itemActions->addWidget(removeItem);
    layout->addLayout(itemActions);
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
        m_originalImage = {}; m_items->setRowCount(0); m_items->hide();
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
    const bool editable = !m_busy && !m_ocrBusy;
    m_image->setEnabled(editable);
    m_items->setEnabled(editable);
    m_title->setEnabled(editable);
    m_body->setEnabled(editable);
    m_scope->setEnabled(editable);
    m_cancel->setEnabled(editable);
    m_save->setEnabled(editable && !m_title->text().trimmed().isEmpty() && (!m_body->toPlainText().trimmed().isEmpty() || m_items->rowCount() > 0));
}
void MemoryWriteDialog::submit()
{
    if (!m_save->isEnabled() || m_busy) return;
    QJsonObject payload{{QStringLiteral("source_type"), QStringLiteral("MANUAL_CONFIG")},
        {QStringLiteral("scope"), m_scope->currentData().toString()},
        {QStringLiteral("raw"), QJsonObject{{QStringLiteral("title"), m_title->text().trimmed()},
            {QStringLiteral("body"), QJsonObject{{QStringLiteral("text"), m_body->toPlainText().trimmed()}}}}}};
    QJsonArray items;
    for (int row = 0; row < m_items->rowCount(); ++row) {
        auto value = [this, row](int col) { auto *cell = m_items->item(row, col); return cell ? cell->text().trimmed() : QString(); };
        bool valid = false; const double amount = value(3).toDouble(&valid);
        if (!valid || !std::isfinite(amount) || value(1).isEmpty() || value(2).isEmpty()
            || (!value(0).isEmpty() && !QDate::fromString(value(0), Qt::ISODate).isValid())) {
            m_status->setText(tr("请核对第 %1 行：日期、类别、项目和金额。空白日期不会参与按月统计。").arg(row + 1)); return;
        }
        items.append(QJsonObject{{"date", value(0)}, {"category", value(1)}, {"vendor", value(2)}, {"amount", amount}});
    }
    auto raw = payload.value("raw").toObject();
    auto body = raw.value("body").toObject();
    if (!items.isEmpty()) { body.insert("items", items); raw.insert("body", body); }
    if (!m_originalImage.isEmpty()) raw.insert("original_image", m_originalImage);
    if (!items.isEmpty() || !m_originalImage.isEmpty()) payload.insert("source_type", "OCR");
    payload.insert("raw", raw);
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
    if (!m_busy && !m_ocrBusy) QDialog::reject();
}
}
