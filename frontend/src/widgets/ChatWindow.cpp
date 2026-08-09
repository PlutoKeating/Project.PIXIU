#include "widgets/ChatWindow.h"

#include <QApplication>
#include <QCloseEvent>
#include <QEasingCurve>
#include <QHBoxLayout>
#include <QKeyEvent>
#include <QLabel>
#include <QLoggingCategory>
#include <QMouseEvent>
#include <QPainter>
#include <QPropertyAnimation>
#include <QPushButton>
#include <QVBoxLayout>

#include "app/UkuiWindow.h"
#include "widgets/InputBar.h"
#include "widgets/MessageList.h"

Q_LOGGING_CATEGORY(lcChat, "pixiu.chat-window")

ChatWindow::ChatWindow(QWidget *parent)
    : QWidget(parent)
{
    setWindowFlags(Qt::FramelessWindowHint | Qt::Tool);
    setAttribute(Qt::WA_TranslucentBackground);
    setFixedSize(kWindowWidth, kWindowHeight);
    // UKUI 原生窗口装饰（阴影/圆角）；无 KYSDK 环境为 no-op。
    pixiu::decorateUkuiWindow(this, 12);

    // 顶栏：标题 + 同步状态占位 + 记忆面板 + 关闭。
    QLabel *titleLabel = new QLabel(tr("PIXIU 貔貅"), this);
    titleLabel->setObjectName(QStringLiteral("titleLabel"));
    titleLabel->setStyleSheet(QStringLiteral("font-size: 14px; font-weight: bold;"));

    m_statusLabel = new QLabel(tr("● 离线"), this);
    m_statusLabel->setObjectName(QStringLiteral("statusLabel"));
    m_statusLabel->setStyleSheet(QStringLiteral("color: #9aa0a6; font-size: 11px;"));

    QPushButton *settingsButton = new QPushButton(tr("⚙"), this);
    settingsButton->setObjectName(QStringLiteral("settingsButton"));
    settingsButton->setAccessibleName(tr("打开设置"));
    settingsButton->setFlat(true);
    settingsButton->setCursor(Qt::PointingHandCursor);
    connect(settingsButton, &QPushButton::clicked, this, &ChatWindow::settingsRequested);

    QPushButton *panelButton = new QPushButton(tr("记忆"), this);
    panelButton->setObjectName(QStringLiteral("panelButton"));
    panelButton->setAccessibleName(tr("打开记忆面板"));
    panelButton->setFlat(true);
    panelButton->setCursor(Qt::PointingHandCursor);
    connect(panelButton, &QPushButton::clicked, this, &ChatWindow::openPanelRequested);

    QPushButton *closeButton = new QPushButton(tr("✕"), this);
    closeButton->setObjectName(QStringLiteral("closeButton"));
    closeButton->setAccessibleName(tr("关闭聊天框"));
    closeButton->setFlat(true);
    closeButton->setCursor(Qt::PointingHandCursor);
    connect(closeButton, &QPushButton::clicked, this, &ChatWindow::closeRequested);

    QHBoxLayout *topBar = new QHBoxLayout();
    topBar->setContentsMargins(0, 0, 0, 0);
    topBar->setSpacing(8);
    topBar->addWidget(titleLabel);
    topBar->addStretch(1);
    topBar->addWidget(m_statusLabel);
    topBar->addWidget(settingsButton);
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
        emit shown();
    }
    raise();
    activateWindow();
    m_inputBar->focusInput();
}

void ChatWindow::setBackendState(ConnectionState state)
{
    switch (state) {
    case ConnectionState::Connected:
        m_statusLabel->setText(tr("● 在线"));
        m_statusLabel->setStyleSheet(QStringLiteral("color: #188038; font-size: 11px;"));
        m_inputBar->setEnabled(true);
        break;
    case ConnectionState::Connecting:
        m_statusLabel->setText(tr("● 连接中…"));
        m_statusLabel->setStyleSheet(QStringLiteral("color: #b06000; font-size: 11px;"));
        m_inputBar->setEnabled(false);
        break;
    case ConnectionState::Error:
        m_statusLabel->setText(tr("● 服务异常"));
        m_statusLabel->setStyleSheet(QStringLiteral("color: #d93025; font-size: 11px;"));
        m_inputBar->setEnabled(false);
        break;
    case ConnectionState::Disconnected:
    default:
        m_statusLabel->setText(tr("● 离线"));
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

void ChatWindow::mousePressEvent(QMouseEvent *event)
{
    // 无边框窗口：按住空白区域拖动（子控件自行消费事件，不影响按钮/输入）。
    if (event->button() == Qt::LeftButton) {
        m_dragging = true;
        m_dragGlobalOffset = event->globalPos() - frameGeometry().topLeft();
        event->accept();
        return;
    }
    QWidget::mousePressEvent(event);
}

void ChatWindow::mouseMoveEvent(QMouseEvent *event)
{
    if (m_dragging) {
        move(event->globalPos() - m_dragGlobalOffset);
        emit moved(frameGeometry().topLeft());
        event->accept();
        return;
    }
    QWidget::mouseMoveEvent(event);
}

void ChatWindow::mouseReleaseEvent(QMouseEvent *event)
{
    m_dragging = false;
    QWidget::mouseReleaseEvent(event);
}

void ChatWindow::leaveEvent(QEvent *event)
{
    // 防止拖动期间鼠标意外离开窗口后状态残留。
    m_dragging = false;
    QWidget::leaveEvent(event);
}

void ChatWindow::paintEvent(QPaintEvent *event)
{
    Q_UNUSED(event)

    QPainter painter(this);
    painter.setRenderHint(QPainter::Antialiasing);
    painter.setPen(Qt::NoPen);
    // 窗口底色跟随主题 Palette（明暗切换时自动联动）。
    QColor background = QApplication::palette().color(QPalette::Window);
    background.setAlpha(245);
    painter.setBrush(background);
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
