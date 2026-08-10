#include "widgets/InputBar.h"

#include <QApplication>
#include <QFile>
#include <QHBoxLayout>
#include <QLineEdit>
#include <QPushButton>

#include "app/UiTokens.h"

InputBar::InputBar(QWidget *parent)
    : QWidget(parent)
{
    // 输入区整体为圆角卡片（浅灰填充、无边框），内部输入框透明无边框，
    // 发送按钮为主题高亮色胶囊——对应侧边助手“低噪声卡片”视觉。
    setObjectName(QStringLiteral("inputBar"));
    // 纯 QWidget 子类需显式启用样式背景，QSS 中的圆角卡片底色才会绘制。
    setAttribute(Qt::WA_StyledBackground, true);

    QPushButton *attachButton = new QPushButton(tr("📎"), this);
    attachButton->setObjectName(QStringLiteral("attachButton"));
    attachButton->setAccessibleName(tr("录入图片或文件"));
    attachButton->setFlat(true);
    // 录入对话框已实现（图片拖入预览 + MANUAL_CONFIG 载荷），文案不再标注“后续”。
    attachButton->setToolTip(tr("录入图片/文件"));
    attachButton->setCursor(Qt::PointingHandCursor);
    connect(attachButton, &QPushButton::clicked, this, &InputBar::attachRequested);

    m_lineEdit = new QLineEdit(this);
    m_lineEdit->setObjectName(QStringLiteral("lineEdit"));
    m_lineEdit->setAccessibleName(tr("问题输入框"));
    m_lineEdit->setPlaceholderText(tr("输入问题，或拖入图片录入…"));
    m_lineEdit->setClearButtonEnabled(true);
    connect(m_lineEdit, &QLineEdit::returnPressed, this, &InputBar::onReturnPressed);

    m_sendButton = new QPushButton(tr("发送"), this);
    m_sendButton->setObjectName(QStringLiteral("sendButton"));
    m_sendButton->setAccessibleName(tr("发送"));
    m_sendButton->setCursor(Qt::PointingHandCursor);
    m_sendButton->setEnabled(false);
    m_sendButton->setStyleSheet(ui::accentButtonStyle());
    connect(m_sendButton, &QPushButton::clicked, this, &InputBar::onSendClicked);
    connect(m_lineEdit, &QLineEdit::textChanged, this, [this](const QString &text) {
        m_sendButton->setEnabled(!text.trimmed().isEmpty());
    });
    // 明暗主题切换时重建胶囊底色（跟随 Highlight，禁用态保持柔和）。
    connect(qApp, &QApplication::paletteChanged, this, [this](const QPalette &) {
        if (m_sendButton) {
            m_sendButton->setStyleSheet(ui::accentButtonStyle());
        }
    });

    QHBoxLayout *layout = new QHBoxLayout(this);
    layout->setContentsMargins(6, 6, 6, 6);
    layout->setSpacing(ui::Spacing::XS);
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
