#include "widgets/ImportDialog.h"

#include <QComboBox>
#include <QDialogButtonBox>
#include <QFormLayout>
#include <QLabel>
#include <QLineEdit>
#include <QPlainTextEdit>
#include <QPushButton>
#include <QVBoxLayout>

ImportDialog::ImportDialog(QWidget *parent)
    : QDialog(parent)
{
    setWindowTitle(QStringLiteral("录入记忆"));
    setModal(false);
    resize(420, 320);

    QLabel *titleLabel = new QLabel(QStringLiteral("标题"), this);
    m_titleEdit = new QLineEdit(this);
    m_titleEdit->setPlaceholderText(QStringLiteral("如：2026年4月家庭支出清单"));

    QLabel *contentLabel = new QLabel(QStringLiteral("内容"), this);
    m_contentEdit = new QPlainTextEdit(this);
    m_contentEdit->setPlaceholderText(QStringLiteral("粘贴文本内容，或后续拖入图片走 OCR 识别…"));

    QLabel *scopeLabel = new QLabel(QStringLiteral("作用域"), this);
    m_scopeCombo = new QComboBox(this);
    m_scopeCombo->addItem(QStringLiteral("本机（user:local）"), QStringLiteral("user:local"));
    m_scopeCombo->addItem(QStringLiteral("家庭共享（shared:home）"), QStringLiteral("shared:home"));

    QFormLayout *form = new QFormLayout();
    form->addRow(titleLabel, m_titleEdit);
    form->addRow(contentLabel, m_contentEdit);
    form->addRow(scopeLabel, m_scopeCombo);

    QDialogButtonBox *buttons = new QDialogButtonBox(QDialogButtonBox::Cancel
                                                     | QDialogButtonBox::Ok, this);
    QPushButton *okButton = buttons->button(QDialogButtonBox::Ok);
    okButton->setText(QStringLiteral("录入记忆"));
    okButton->setEnabled(false);
    connect(buttons, &QDialogButtonBox::rejected, this, &QDialog::hide);
    connect(buttons, &QDialogButtonBox::accepted, this, &ImportDialog::onConfirmClicked);

    QVBoxLayout *layout = new QVBoxLayout(this);
    layout->addLayout(form);
    layout->addWidget(buttons);

    connect(m_titleEdit, &QLineEdit::textChanged, this, [this, okButton](const QString &text) {
        okButton->setEnabled(!text.trimmed().isEmpty()
                             && !m_contentEdit->toPlainText().trimmed().isEmpty());
    });
    connect(m_contentEdit, &QPlainTextEdit::textChanged, this, [this, okButton]() {
        okButton->setEnabled(!m_titleEdit->text().trimmed().isEmpty()
                             && !m_contentEdit->toPlainText().trimmed().isEmpty());
    });
}

void ImportDialog::onConfirmClicked()
{
    const QString title = m_titleEdit->text().trimmed();
    const QString content = m_contentEdit->toPlainText().trimmed();
    const QString scope = m_scopeCombo->currentData().toString();
    if (title.isEmpty() || content.isEmpty()) {
        return;
    }
    emit importRequested(title, content, scope);
    hide();
    m_titleEdit->clear();
    m_contentEdit->clear();
}
