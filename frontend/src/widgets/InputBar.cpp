#include "widgets/InputBar.h"

#include <QHBoxLayout>
#include <QLineEdit>
#include <QPushButton>

InputBar::InputBar(QWidget *parent)
    : QWidget(parent)
{
    QPushButton *attachButton = new QPushButton(tr("📎"), this);
    attachButton->setObjectName(QStringLiteral("attachButton"));
    attachButton->setFlat(true);
    attachButton->setToolTip(tr("录入图片/文件（后续 feature）"));
    attachButton->setCursor(Qt::PointingHandCursor);
    connect(attachButton, &QPushButton::clicked, this, &InputBar::attachRequested);

    m_lineEdit = new QLineEdit(this);
    m_lineEdit->setObjectName(QStringLiteral("lineEdit"));
    m_lineEdit->setPlaceholderText(tr("输入问题，或拖入图片录入…"));
    m_lineEdit->setClearButtonEnabled(true);
    connect(m_lineEdit, &QLineEdit::returnPressed, this, &InputBar::onReturnPressed);

    m_sendButton = new QPushButton(tr("发送"), this);
    m_sendButton->setObjectName(QStringLiteral("sendButton"));
    m_sendButton->setCursor(Qt::PointingHandCursor);
    m_sendButton->setEnabled(false);
    connect(m_sendButton, &QPushButton::clicked, this, &InputBar::onSendClicked);
    connect(m_lineEdit, &QLineEdit::textChanged, this, [this](const QString &text) {
        m_sendButton->setEnabled(!text.trimmed().isEmpty());
    });

    QHBoxLayout *layout = new QHBoxLayout(this);
    layout->setContentsMargins(0, 0, 0, 0);
    layout->setSpacing(8);
    layout->addWidget(attachButton);
    layout->addWidget(m_lineEdit, 1);
    layout->addWidget(m_sendButton);
}

void InputBar::focusInput()
{
    m_lineEdit->setFocus(Qt::ShortcutFocusReason);
}

void InputBar::clearInput()
{
    m_lineEdit->clear();
}

void InputBar::setInputText(const QString &text)
{
    m_lineEdit->setText(text);
    m_lineEdit->setFocus(Qt::OtherFocusReason);
}

void InputBar::onSendClicked()
{
    const QString text = m_lineEdit->text().trimmed();
    if (text.isEmpty()) {
        return;
    }
    emit sendRequested(text);
    clearInput();
}

void InputBar::onReturnPressed()
{
    onSendClicked();
}
