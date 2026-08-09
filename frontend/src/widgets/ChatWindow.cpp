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
#include "app/UiIcons.h"
#include "app/UiTokens.h"
#include "widgets/InputBar.h"
#include "widgets/MessageList.h"

Q_LOGGING_CATEGORY(lcChat, "pixiu.chat-window")

ChatWindow::ChatWindow(QWidget *parent)
    : QWidget(parent)
{
    setWindowFlags(Qt::FramelessWindowHint | Qt::Tool);
    setAttribute(Qt::WA_TranslucentBackground);
    resize(kWindowWidth, kWindowHeight);
    setMinimumSize(kMinWidth, kMinHeight);
    // UKUI 原生窗口装饰（阴影/圆角）；无 KYSDK 环境为 no-op。
    pixiu::decorateUkuiWindow(this, ui::Radius::Window);

    // 顶栏：标题 + 同步状态占位 + 记忆面板 + 关闭。
    QLabel *titleLabel = new QLabel(tr("PIXIU 貔貅"), this);
    titleLabel->setObjectName(QStringLiteral("titleLabel"));

    m_statusLabel = new QLabel(tr("● 离线"), this);
    m_statusLabel->setObjectName(QStringLiteral("statusLabel"));
    m_statusLabel->setStyleSheet(ui::textStyle(ui::Role::Muted));

    m_settingsButton = new QPushButton(this);
    m_settingsButton->setObjectName(QStringLiteral("settingsButton"));
    m_settingsButton->setAccessibleName(tr("打开设置"));
    m_settingsButton->setFlat(true);
    m_settingsButton->setCursor(Qt::PointingHandCursor);
    // 设置入口统一使用运行时绘制齿轮图标：颜色跟随主题 Palette，HiDPI 多倍图。
    m_settingsButton->setIcon(ui::gearIcon(QApplication::palette()));
    m_settingsButton->setIconSize(QSize(16, 16));
    connect(m_settingsButton, &QPushButton::clicked,
            this, &ChatWindow::settingsRequested);
    // 明暗主题切换时重建图标颜色（ThemeService 应用 Palette 后触发）。
    connect(qApp, &QApplication::paletteChanged, this,
            [this](const QPalette &palette) {
                if (m_settingsButton) {
                    m_settingsButton->setIcon(ui::gearIcon(palette));
                }
            });

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
    topBar->setSpacing(ui::Spacing::S);
    topBar->addWidget(titleLabel);
    topBar->addStretch(1);
    topBar->addWidget(m_statusLabel);
    topBar->addWidget(m_settingsButton);
    topBar->addWidget(panelButton);
    topBar->addWidget(closeButton);

    m_messageList = new MessageList(this);

    m_inputBar = new InputBar(this);
    connect(m_inputBar, &InputBar::sendRequested, this, &ChatWindow::sendRequested);
    connect(m_inputBar, &InputBar::attachRequested, this, &ChatWindow::attachRequested);

    QVBoxLayout *layout = new QVBoxLayout(this);
    layout->setContentsMargins(ui::Spacing::L, ui::Spacing::M,
                               ui::Spacing::L, ui::Spacing::L);
    layout->setSpacing(ui::Spacing::S);
    layout->addLayout(topBar);
    layout->addWidget(m_messageList, 1);
    layout->addWidget(m_inputBar);

    updateResizeCursor(QPoint(0, 0));
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
        m_statusLabel->setStyleSheet(ui::textStyle(ui::Role::Success));
        m_inputBar->setEnabled(true);
        break;
    case ConnectionState::Connecting:
        m_statusLabel->setText(tr("● 连接中…"));
        m_statusLabel->setStyleSheet(ui::textStyle(ui::Role::Warning));
        m_inputBar->setEnabled(false);
        break;
    case ConnectionState::Error:
        m_statusLabel->setText(tr("● 服务异常"));
        m_statusLabel->setStyleSheet(ui::textStyle(ui::Role::Error));
        m_inputBar->setEnabled(false);
        break;
    case ConnectionState::Disconnected:
    default:
        m_statusLabel->setText(tr("● 离线"));
        m_statusLabel->setStyleSheet(ui::textStyle(ui::Role::Muted));
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
    m_resizeEdge = resizeEdgeAt(event->pos());
    if (m_resizeEdge != ResizeEdge::None) {
        m_resizing = true;
        m_resizeStartGeometry = geometry();
        m_resizeStartGlobalPos = event->globalPos();
        event->accept();
        return;
    }
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
    if (m_resizing) {
        const QPoint delta = event->globalPos() - m_resizeStartGlobalPos;
        QRect geometry = m_resizeStartGeometry;
        switch (m_resizeEdge) {
        case ResizeEdge::Left:
        case ResizeEdge::TopLeft:
        case ResizeEdge::BottomLeft:
            geometry.setLeft(geometry.left() + delta.x());
            break;
        case ResizeEdge::Right:
        case ResizeEdge::TopRight:
        case ResizeEdge::BottomRight:
            geometry.setRight(geometry.right() + delta.x());
            break;
        default:
            break;
        }
        switch (m_resizeEdge) {
        case ResizeEdge::Top:
        case ResizeEdge::TopLeft:
        case ResizeEdge::TopRight:
            geometry.setTop(geometry.top() + delta.y());
            break;
        case ResizeEdge::Bottom:
        case ResizeEdge::BottomLeft:
        case ResizeEdge::BottomRight:
            geometry.setBottom(geometry.bottom() + delta.y());
            break;
        default:
            break;
        }
        // 最小尺寸钳制（拖动左/上边缘时锚定对边）。
        if (geometry.width() < kMinWidth) {
            if (m_resizeEdge == ResizeEdge::Left
                || m_resizeEdge == ResizeEdge::TopLeft
                || m_resizeEdge == ResizeEdge::BottomLeft) {
                geometry.setLeft(geometry.right() - kMinWidth + 1);
            } else {
                geometry.setRight(geometry.left() + kMinWidth - 1);
            }
        }
        if (geometry.height() < kMinHeight) {
            if (m_resizeEdge == ResizeEdge::Top
                || m_resizeEdge == ResizeEdge::TopLeft
                || m_resizeEdge == ResizeEdge::TopRight) {
                geometry.setTop(geometry.bottom() - kMinHeight + 1);
            } else {
                geometry.setBottom(geometry.top() + kMinHeight - 1);
            }
        }
        setGeometry(geometry);
        event->accept();
        return;
    }
    if (m_dragging) {
        move(event->globalPos() - m_dragGlobalOffset);
        emit moved(frameGeometry().topLeft());
        event->accept();
        return;
    }
    updateResizeCursor(event->pos());
    QWidget::mouseMoveEvent(event);
}

void ChatWindow::mouseReleaseEvent(QMouseEvent *event)
{
    m_dragging = false;
    m_resizing = false;
    updateResizeCursor(event->pos());
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
    painter.drawRoundedRect(rect(), ui::Radius::Window, ui::Radius::Window);
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

ChatWindow::ResizeEdge ChatWindow::resizeEdgeAt(const QPoint &pos) const
{
    const bool left = pos.x() <= kResizeMargin;
    const bool right = pos.x() >= width() - 1 - kResizeMargin;
    const bool top = pos.y() <= kResizeMargin;
    const bool bottom = pos.y() >= height() - 1 - kResizeMargin;
    if (left && top) return ResizeEdge::TopLeft;
    if (right && top) return ResizeEdge::TopRight;
    if (left && bottom) return ResizeEdge::BottomLeft;
    if (right && bottom) return ResizeEdge::BottomRight;
    if (left) return ResizeEdge::Left;
    if (right) return ResizeEdge::Right;
    if (top) return ResizeEdge::Top;
    if (bottom) return ResizeEdge::Bottom;
    return ResizeEdge::None;
}

void ChatWindow::updateResizeCursor(const QPoint &pos)
{
    if (m_resizing) {
        return;
    }
    switch (resizeEdgeAt(pos)) {
    case ResizeEdge::Left:
    case ResizeEdge::Right:
        setCursor(Qt::SizeHorCursor);
        break;
    case ResizeEdge::Top:
    case ResizeEdge::Bottom:
        setCursor(Qt::SizeVerCursor);
        break;
    case ResizeEdge::TopLeft:
    case ResizeEdge::BottomRight:
        setCursor(Qt::SizeFDiagCursor);
        break;
    case ResizeEdge::TopRight:
    case ResizeEdge::BottomLeft:
        setCursor(Qt::SizeBDiagCursor);
        break;
    default:
        unsetCursor();
        break;
    }
}
