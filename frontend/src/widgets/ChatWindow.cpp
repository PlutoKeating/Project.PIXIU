#include "widgets/ChatWindow.h"

#include <QApplication>
#include <QCloseEvent>
#include <QAbstractItemModel>
#include <QEasingCurve>
#include <QHBoxLayout>
#include <QIcon>
#include <QKeyEvent>
#include <QLabel>
#include <QLoggingCategory>
#include <QMouseEvent>
#include <QPainter>
#include <QPropertyAnimation>
#include <QPushButton>
#include <QStackedWidget>
#include <QTimer>
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

    // 顶栏：Logo + 标题 + 同步状态 + 设置/记忆面板/关闭。
    QLabel *logoLabel = new QLabel(this);
    const QIcon brandIcon(QStringLiteral(":/icons/pixiu.svg"));
    if (!brandIcon.isNull()) {
        logoLabel->setPixmap(brandIcon.pixmap(QSize(20, 20)));
    }
    logoLabel->setFixedSize(22, 22);
    logoLabel->setAccessibleName(tr("PIXIU 标识"));

    QLabel *titleLabel = new QLabel(tr("PIXIU 貔貅"), this);
    titleLabel->setObjectName(QStringLiteral("titleLabel"));

    m_statusLabel = new QLabel(tr("● 离线"), this);
    m_statusLabel->setObjectName(QStringLiteral("statusLabel"));
    m_statusLabel->setStyleSheet(ui::textStyle(ui::Role::Muted));
    // 状态文案长度不同（在线/连接中/服务异常/离线），固定最小宽度，
    // 避免状态切换时右侧按钮左右抖动（ARCHITECTURE §7.3 轻量克制）。
    const QString states[] = {tr("● 在线"), tr("● 连接中…"),
                              tr("● 服务异常"), tr("● 离线")};
    int widestState = 0;
    for (const QString &text : states) {
        widestState = qMax(widestState,
                           m_statusLabel->fontMetrics().horizontalAdvance(text));
    }
    m_statusLabel->setMinimumWidth(widestState + ui::Spacing::S);

    m_settingsButton = new QPushButton(this);
    m_settingsButton->setObjectName(QStringLiteral("settingsButton"));
    m_settingsButton->setAccessibleName(tr("打开设置"));
    m_settingsButton->setToolTip(tr("打开设置"));
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
    panelButton->setToolTip(tr("打开记忆面板"));
    panelButton->setFlat(true);
    panelButton->setCursor(Qt::PointingHandCursor);
    connect(panelButton, &QPushButton::clicked, this, &ChatWindow::openPanelRequested);

    QPushButton *closeButton = new QPushButton(tr("✕"), this);
    closeButton->setObjectName(QStringLiteral("closeButton"));
    closeButton->setAccessibleName(tr("关闭聊天框"));
    closeButton->setToolTip(tr("关闭聊天框"));
    closeButton->setFlat(true);
    closeButton->setCursor(Qt::PointingHandCursor);
    connect(closeButton, &QPushButton::clicked, this, &ChatWindow::closeRequested);

    QHBoxLayout *topBar = new QHBoxLayout();
    topBar->setContentsMargins(0, 0, 0, 0);
    topBar->setSpacing(ui::Spacing::S);
    topBar->addWidget(logoLabel);
    topBar->addWidget(titleLabel);
    topBar->addStretch(1);
    topBar->addWidget(m_statusLabel);
    topBar->addWidget(m_settingsButton);
    topBar->addWidget(panelButton);
    topBar->addWidget(closeButton);

    // 消息区：欢迎空态 + 消息流（消息到达后自动切换，清空后回到欢迎页）。
    m_messageList = new MessageList(this);
    m_welcomeView = buildWelcomeView();
    m_centerStack = new QStackedWidget(this);
    m_centerStack->addWidget(m_welcomeView);
    m_centerStack->addWidget(m_messageList);
    m_centerStack->setCurrentWidget(m_welcomeView);
    connect(m_messageList->model(), &QAbstractItemModel::rowsInserted, this,
            [this]() {
                if (m_centerStack && m_messageList) {
                    m_centerStack->setCurrentWidget(m_messageList);
                }
            });
    // 注意：本机 Qt 版本中 QListWidget::clear() 不发 rowsRemoved，而是发
    // modelReset（实测确认）；两者都接入同一延迟判定，保证清空后回到欢迎页。
    const auto resetWelcome = [this]() {
        // 延迟一帧判断：思考占位被答案替换时先清空再插入，避免欢迎页
        // 在两次行变更之间闪现。
        QTimer::singleShot(0, this, [this]() {
            if (m_centerStack && m_messageList
                && m_messageList->count() == 0) {
                m_centerStack->setCurrentWidget(m_welcomeView);
            }
        });
    };
    connect(m_messageList->model(), &QAbstractItemModel::rowsRemoved,
            this, resetWelcome);
    connect(m_messageList->model(), &QAbstractItemModel::modelReset,
            this, resetWelcome);

    m_inputBar = new InputBar(this);
    connect(m_inputBar, &InputBar::sendRequested, this, &ChatWindow::sendRequested);
    connect(m_inputBar, &InputBar::attachRequested, this, &ChatWindow::attachRequested);

    QVBoxLayout *layout = new QVBoxLayout(this);
    layout->setContentsMargins(ui::Spacing::L, ui::Spacing::M,
                               ui::Spacing::L, ui::Spacing::L);
    layout->setSpacing(ui::Spacing::S);
    layout->addLayout(topBar);
    layout->addWidget(m_centerStack, 1);
    layout->addWidget(m_inputBar);

    updateResizeCursor(QPoint(0, 0));
}

QWidget *ChatWindow::buildWelcomeView()
{
    QWidget *view = new QWidget(this);
    view->setObjectName(QStringLiteral("welcomeView"));
    view->setAccessibleName(tr("PIXIU 欢迎页"));

    QLabel *logo = new QLabel(view);
    const QIcon brandIcon(QStringLiteral(":/icons/pixiu.svg"));
    if (!brandIcon.isNull()) {
        logo->setPixmap(brandIcon.pixmap(QSize(52, 52)));
    }
    logo->setAlignment(Qt::AlignCenter);
    logo->setAccessibleName(tr("PIXIU 标识"));

    QLabel *title = new QLabel(tr("你好，我是 PIXIU"), view);
    title->setObjectName(QStringLiteral("welcomeTitle"));
    title->setAlignment(Qt::AlignCenter);

    QLabel *subtitle = new QLabel(tr("问问你的记忆，或录入新的知识"), view);
    subtitle->setObjectName(QStringLiteral("welcomeSubtitle"));
    subtitle->setAlignment(Qt::AlignCenter);
    subtitle->setWordWrap(true);

    QPushButton *askButton = new QPushButton(tr("开始提问"), view);
    askButton->setObjectName(QStringLiteral("welcomeAction"));
    askButton->setAccessibleName(tr("开始提问"));
    askButton->setCursor(Qt::PointingHandCursor);
    connect(askButton, &QPushButton::clicked, this, [this]() {
        if (m_inputBar) {
            m_inputBar->focusInput();
        }
    });

    QPushButton *importButton = new QPushButton(tr("录入知识"), view);
    importButton->setObjectName(QStringLiteral("welcomeAction"));
    importButton->setAccessibleName(tr("录入知识"));
    importButton->setCursor(Qt::PointingHandCursor);
    connect(importButton, &QPushButton::clicked,
            this, &ChatWindow::attachRequested);

    QPushButton *panelButton = new QPushButton(tr("记忆面板"), view);
    panelButton->setObjectName(QStringLiteral("welcomeAction"));
    panelButton->setAccessibleName(tr("打开记忆面板"));
    panelButton->setCursor(Qt::PointingHandCursor);
    connect(panelButton, &QPushButton::clicked,
            this, &ChatWindow::openPanelRequested);

    QHBoxLayout *actions = new QHBoxLayout();
    actions->setContentsMargins(0, 0, 0, 0);
    actions->setSpacing(ui::Spacing::S);
    actions->addStretch(1);
    actions->addWidget(askButton);
    actions->addWidget(importButton);
    actions->addWidget(panelButton);
    actions->addStretch(1);

    QLabel *hint = new QLabel(tr("按 Ctrl+Alt+P 随时唤起"), view);
    hint->setObjectName(QStringLiteral("welcomeHint"));
    hint->setAlignment(Qt::AlignCenter);

    QVBoxLayout *layout = new QVBoxLayout(view);
    layout->setContentsMargins(ui::Spacing::XL, ui::Spacing::XL,
                               ui::Spacing::XL, ui::Spacing::L);
    layout->addStretch(1);
    layout->addWidget(logo);
    layout->addSpacing(ui::Spacing::M);
    layout->addWidget(title);
    layout->addSpacing(ui::Spacing::XS);
    layout->addWidget(subtitle);
    layout->addSpacing(ui::Spacing::XL);
    layout->addLayout(actions);
    layout->addStretch(1);
    layout->addWidget(hint);
    return view;
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
