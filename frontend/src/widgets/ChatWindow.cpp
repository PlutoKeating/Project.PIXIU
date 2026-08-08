#include "widgets/ChatWindow.h"

#include <QCloseEvent>
#include <QEasingCurve>
#include <QHBoxLayout>
#include <QKeyEvent>
#include <QLabel>
#include <QLoggingCategory>
#include <QPainter>
#include <QPropertyAnimation>
#include <QPushButton>
#include <QVBoxLayout>

#include "widgets/InputBar.h"
#include "widgets/MessageList.h"

Q_LOGGING_CATEGORY(lcChat, "pixiu.chat-window")

ChatWindow::ChatWindow(QWidget *parent)
    : QWidget(parent)
{
    setWindowFlags(Qt::FramelessWindowHint | Qt::Tool);
    setAttribute(Qt::WA_TranslucentBackground);
    setFixedSize(kWindowWidth, kWindowHeight);

    // 顶栏：标题 + 同步状态占位 + 记忆面板 + 关闭。
    QLabel *titleLabel = new QLabel(QStringLiteral("PIXIU 貔貅"), this);
    titleLabel->setStyleSheet(QStringLiteral("font-size: 14px; font-weight: bold;"));

    m_statusLabel = new QLabel(QStringLiteral("● 离线"), this);
    m_statusLabel->setStyleSheet(QStringLiteral("color: #9aa0a6; font-size: 11px;"));

    QPushButton *panelButton = new QPushButton(QStringLiteral("记忆"), this);
    panelButton->setFlat(true);
    panelButton->setCursor(Qt::PointingHandCursor);
    connect(panelButton, &QPushButton::clicked, this, &ChatWindow::openPanelRequested);

    QPushButton *closeButton = new QPushButton(QStringLiteral("✕"), this);
    closeButton->setFlat(true);
    closeButton->setCursor(Qt::PointingHandCursor);
    connect(closeButton, &QPushButton::clicked, this, &ChatWindow::closeRequested);

    QHBoxLayout *topBar = new QHBoxLayout();
    topBar->setContentsMargins(0, 0, 0, 0);
    topBar->setSpacing(8);
    topBar->addWidget(titleLabel);
    topBar->addStretch(1);
    topBar->addWidget(m_statusLabel);
    topBar->addWidget(panelButton);
    topBar->addWidget(closeButton);

    m_messageList = new MessageList(this);

    m_inputBar = new InputBar(this);
    connect(m_inputBar, &InputBar::sendRequested, this, &ChatWindow::sendRequested);
    connect(m_inputBar, &InputBar::attachRequested, this, &ChatWindow::attachRequested);

    QVBoxLayout *layout = new QVBoxLayout(this);
    layout->setContentsMargins(16, 12, 16, 16);
    layout->setSpacing(8);
    layout->addLayout(topBar);
    layout->addWidget(m_messageList, 1);
    layout->addWidget(m_inputBar);
}

MessageList *ChatWindow::messageList() const
{
    return m_messageList;
}

void ChatWindow::showAndFocus()
{
    if (!isVisible()) {
        show();
        animateOpacity(1.0);
    }
    raise();
    activateWindow();
    m_inputBar->focusInput();
}

void ChatWindow::setBackendState(ConnectionState state)
{
    switch (state) {
    case ConnectionState::Connected:
        m_statusLabel->setText(QStringLiteral("● 在线"));
        m_statusLabel->setStyleSheet(QStringLiteral("color: #188038; font-size: 11px;"));
        m_inputBar->setEnabled(true);
        break;
    case ConnectionState::Connecting:
        m_statusLabel->setText(QStringLiteral("● 连接中…"));
        m_statusLabel->setStyleSheet(QStringLiteral("color: #b06000; font-size: 11px;"));
        m_inputBar->setEnabled(false);
        break;
    case ConnectionState::Error:
        m_statusLabel->setText(QStringLiteral("● 服务异常"));
        m_statusLabel->setStyleSheet(QStringLiteral("color: #d93025; font-size: 11px;"));
        m_inputBar->setEnabled(false);
        break;
    case ConnectionState::Disconnected:
    default:
        m_statusLabel->setText(QStringLiteral("● 离线"));
        m_statusLabel->setStyleSheet(QStringLiteral("color: #9aa0a6; font-size: 11px;"));
        m_inputBar->setEnabled(false);
        break;
    }
}

void ChatWindow::restoreInput(const QString &text)
{
    m_inputBar->setInputText(text);
}

void ChatWindow::hideAnimated()
{
    if (!isVisible()) {
        return;
    }
    animateOpacity(0.0);
}

bool ChatWindow::isChatVisible() const
{
    return isVisible();
}

void ChatWindow::keyPressEvent(QKeyEvent *event)
{
    if (event->key() == Qt::Key_Escape) {
        hideAnimated();
        event->accept();
        return;
    }
    QWidget::keyPressEvent(event);
}

void ChatWindow::paintEvent(QPaintEvent *event)
{
    Q_UNUSED(event)

    QPainter painter(this);
    painter.setRenderHint(QPainter::Antialiasing);
    painter.setPen(Qt::NoPen);
    painter.setBrush(QColor(0xFC, 0xFC, 0xFC, 245));
    painter.drawRoundedRect(rect(), 12, 12);
}

void ChatWindow::moveEvent(QMoveEvent *event)
{
    m_rememberedPos = event->pos();
    QWidget::moveEvent(event);
}

void ChatWindow::closeEvent(QCloseEvent *event)
{
    // 关闭按钮语义为隐藏，而非销毁。
    hideAnimated();
    event->ignore();
}

void ChatWindow::animateOpacity(qreal target)
{
    if (!m_opacityAnimation) {
        m_opacityAnimation = new QPropertyAnimation(this, "windowOpacity", this);
        m_opacityAnimation->setDuration(kAnimationMs);
        m_opacityAnimation->setEasingCurve(QEasingCurve::OutCubic);
        connect(m_opacityAnimation, &QPropertyAnimation::finished, this, [this]() {
            if (windowOpacity() <= 0.01) {
                hide();
            }
        });
    }
    m_opacityAnimation->stop();
    m_opacityAnimation->setStartValue(windowOpacity());
    m_opacityAnimation->setEndValue(target);
    m_opacityAnimation->start();
}
