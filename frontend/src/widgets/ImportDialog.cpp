#include "widgets/ImportDialog.h"

#include "app/UiTokens.h"

#include <QComboBox>
#include <QDialogButtonBox>
#include <QDragEnterEvent>
#include <QDropEvent>
#include <QFormLayout>
#include <QLabel>
#include <QLineEdit>
#include <QMimeData>
#include <QPlainTextEdit>
#include <QPixmap>
#include <QPushButton>
#include <QUrl>
#include <QVBoxLayout>

ImportDialog::ImportDialog(QWidget *parent)
    : QDialog(parent)
{
    setWindowTitle(tr("录入记忆"));
    setModal(false);
    resize(420, 320);
    setAcceptDrops(true);

    QLabel *titleLabel = new QLabel(tr("标题"), this);
    m_titleEdit = new QLineEdit(this);
    m_titleEdit->setPlaceholderText(tr("如：2026年4月家庭支出清单"));

    QLabel *contentLabel = new QLabel(tr("内容"), this);
    m_contentEdit = new QPlainTextEdit(this);
    m_contentEdit->setPlaceholderText(
        tr("粘贴文本内容；也可拖入图片作为附件预览…"));

    QLabel *scopeLabel = new QLabel(tr("作用域"), this);
    m_scopeCombo = new QComboBox(this);
    m_scopeCombo->addItem(tr("本机（user:local）"), QStringLiteral("user:local"));
    m_scopeCombo->addItem(tr("家庭共享（shared:home）"), QStringLiteral("shared:home"));

    m_previewLabel = new QLabel(
        tr("可拖入图片，录入时附带附件预览（OCR 接入后自动识别）"), this);
    m_previewLabel->setObjectName(QStringLiteral("previewLabel"));
    m_previewLabel->setAlignment(Qt::AlignCenter);
    m_previewLabel->setMinimumHeight(64);

    QFormLayout *form = new QFormLayout();
    form->addRow(titleLabel, m_titleEdit);
    form->addRow(contentLabel, m_contentEdit);
    form->addRow(scopeLabel, m_scopeCombo);
    form->addRow(QString(), m_previewLabel);

    QDialogButtonBox *buttons = new QDialogButtonBox(QDialogButtonBox::Cancel
                                                     | QDialogButtonBox::Ok, this);
    QPushButton *okButton = buttons->button(QDialogButtonBox::Ok);
    okButton->setText(tr("录入记忆"));
    okButton->setEnabled(false);
    okButton->setCursor(Qt::PointingHandCursor);
    QPushButton *cancelButton = buttons->button(QDialogButtonBox::Cancel);
    cancelButton->setCursor(Qt::PointingHandCursor);
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
    emit importRequested(title, content, scope, m_imagePath);
    hide();
    m_titleEdit->clear();
    m_contentEdit->clear();
    m_imagePath.clear();
    m_previewLabel->setText(
        tr("可拖入图片，录入时附带附件预览（OCR 接入后自动识别）"));
}

void ImportDialog::dragEnterEvent(QDragEnterEvent *event)
{
    if (event->mimeData()->hasUrls()) {
        const QList<QUrl> urls = event->mimeData()->urls();
        for (const QUrl &url : urls) {
            if (url.isLocalFile()
                && QPixmap(url.toLocalFile()).isNull() == false) {
                event->acceptProposedAction();
                return;
            }
        }
    }
    if (event->mimeData()->hasImage()) {
        event->acceptProposedAction();
    }
}

void ImportDialog::dropEvent(QDropEvent *event)
{
    if (event->mimeData()->hasUrls()) {
        const QList<QUrl> urls = event->mimeData()->urls();
        for (const QUrl &url : urls) {
            if (url.isLocalFile()) {
                const QString path = url.toLocalFile();
                if (!QPixmap(path).isNull()) {
                    setPreviewImage(path);
                    event->acceptProposedAction();
                    return;
                }
            }
        }
    }
    QDialog::dropEvent(event);
}

void ImportDialog::setPreviewImage(const QString &path)
{
    m_imagePath = path;
    const QPixmap source(path);
    m_previewLabel->setPixmap(source.scaled(
        QSize(96, 96), Qt::KeepAspectRatio, Qt::SmoothTransformation));
    m_previewLabel->setToolTip(path);
}
