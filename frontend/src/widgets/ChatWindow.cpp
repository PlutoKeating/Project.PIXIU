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
#include <QMenu>
#include <QMouseEvent>
#include <QPainter>
#include <QPropertyAnimation>
#include <QPushButton>
#include <QScrollArea>
#include <QStackedWidget>
#include <QTimer>
#include <QVBoxLayout>

#include "app/UkuiWindow.h"
#include "app/UiIcons.h"
#include "app/UiTokens.h"
#include "widgets/InputBar.h"
#include "widgets/MessageList.h"

Q_LOGGING_CATEGORY(lcChat, "pixiu.chat-window")

namespace {

// 建议问题卡片：浅灰圆角、无强边框，左侧弱图标 + 可换行长文案；
// hover 只做轻微背景变化（QSS），点击由 ChatWindow 接线（填入输入框）。
class SuggestionCard : public QPushButton
{
public:
    explicit SuggestionCard(const QString &text, QWidget *parent = nullptr)
        : QPushButton(parent)
    {
        setObjectName(QStringLiteral("suggestionCard"));
        setFlat(true);
        setCursor(Qt::PointingHandCursor);
        setAccessibleName(text);
        setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Fixed);

        QHBoxLayout *layout = new QHBoxLayout(this);
        layout->setContentsMargins(ui::Spacing::M, 10, ui::Spacing::M, 10);
        layout->setSpacing(10);
        m_iconLabel = new QLabel(this);
        m_iconLabel->setObjectName(QStringLiteral("suggestionIcon"));
        layout->addWidget(m_iconLabel, 0, Qt::AlignTop);
        m_textLabel = new QLabel(text, this);
        m_textLabel->setObjectName(QStringLiteral("suggestionText"));
        m_textLabel->setWordWrap(true);
        m_textLabel->setTextInteractionFlags(Qt::NoTextInteraction);
        layout->addWidget(m_textLabel, 1);
    }

    // QPushButton 默认 sizeHint 只按自身文本/图标计算，不理会内部布局；
    // 这里改为按文本在典型宽度下的换行高度计算，保证中/英文长文案的
    // 建议卡片高度正确（中文 1 行、英文 2 行内均不裁剪）。
    QSize sizeHint() const override
    {
        constexpr int kTextWidth = 230;
        const int textHeight = m_textLabel
                                   ? m_textLabel->heightForWidth(kTextWidth)
                                   : 0;
        const int vMargins = 20;   // 上下内边距 10px × 2
        const int hMargins = 34;   // 左右内边距 24px + 图标/文字间距 10px
        return QSize(kTextWidth + hMargins,
                     qMax(52, textHeight + vMargins));
    }

private:
    QLabel *m_iconLabel = nullptr;
    QLabel *m_textLabel = nullptr;
};

} // namespace

ChatWindow::ChatWindow(QWidget *parent)
    : QWidget(parent)
{
    setWindowFlags(Qt::FramelessWindowHint | Qt::Tool);
    setAttribute(Qt::WA_TranslucentBackground);
    resize(kWindowWidth, kWindowHeight);
    setMinimumSize(kMinWidth, kMinHeight);
    // UKUI 原生窗口装饰（阴影/圆角）；无 KYSDK 环境为 no-op。
    pixiu::decorateUkuiWindow(this, ui::Radius::Window);

    // 顶栏：Logo + 应用入口（左侧），置顶/菜单/关闭（右侧），轻量留白。
    QLabel *logoLabel = new QLabel(this);
    const QIcon brandIcon(QStringLiteral(":/icons/pixiu.svg"));
    if (!brandIcon.isNull()) {
        logoLabel->setPixmap(brandIcon.pixmap(QSize(20, 20)));
    }
    logoLabel->setFixedSize(22, 22);
    logoLabel->setAccessibleName(tr("PIXIU 标识"));

    QLabel *titleLabel = new QLabel(tr("PIXIU 貔貅"), this);
    titleLabel->setObjectName(QStringLiteral("titleLabel"));

    const auto makeIconButton = [this](const QString &objectName,
                                       const QString &accessibleName,
                                       const QString &toolTip) {
        QPushButton *button = new QPushButton(this);
        button->setObjectName(objectName);
        button->setAccessibleName(accessibleName);
        button->setToolTip(toolTip);
        button->setFlat(true);
        button->setCursor(Qt::PointingHandCursor);
        button->setFixedSize(28, 28);
        button->setIconSize(QSize(16, 16));
        return button;
    };

    m_pinButton = makeIconButton(QStringLiteral("pinButton"),
                                 tr("置顶聊天框"),
                                 tr("置顶"));
    connect(m_pinButton, &QPushButton::clicked,
            this, &ChatWindow::togglePinned);

    m_moreButton = makeIconButton(QStringLiteral("moreButton"),
                                  tr("更多"),
                                  tr("更多"));
    m_topBarMenu = new QMenu(this);
    m_topBarMenu->setObjectName(QStringLiteral("topBarMenu"));
    QAction *panelAction = m_topBarMenu->addAction(tr("记忆面板"));
    QAction *settingsAction = m_topBarMenu->addAction(tr("设置"));
    QAction *importAction = m_topBarMenu->addAction(tr("录入知识"));
    QAction *syncAction = m_topBarMenu->addAction(tr("同步面板"));
    connect(panelAction, &QAction::triggered,
            this, &ChatWindow::openPanelRequested);
    connect(settingsAction, &QAction::triggered,
            this, &ChatWindow::settingsRequested);
    connect(importAction, &QAction::triggered,
            this, &ChatWindow::attachRequested);
    connect(syncAction, &QAction::triggered,
            this, &ChatWindow::syncPanelRequested);
    connect(m_moreButton, &QPushButton::clicked, this, [this]() {
        if (m_topBarMenu) {
            m_topBarMenu->popup(m_moreButton->mapToGlobal(
                QPoint(0, m_moreButton->height())));
        }
    });

    QPushButton *closeButton = new QPushButton(this);
    closeButton->setObjectName(QStringLiteral("closeButton"));
    closeButton->setAccessibleName(tr("关闭聊天框"));
    closeButton->setToolTip(tr("关闭聊天框"));
    closeButton->setFlat(true);
    closeButton->setCursor(Qt::PointingHandCursor);
    closeButton->setFixedSize(28, 28);
    closeButton->setIconSize(QSize(16, 16));
    connect(closeButton, &QPushButton::clicked, this, &ChatWindow::closeRequested);
    connect(qApp, &QApplication::paletteChanged, this,
            [this](const QPalette &) { rebuildTopBarIcons(); });
    rebuildTopBarIcons();

    QHBoxLayout *topBar = new QHBoxLayout();
    topBar->setContentsMargins(0, 0, 0, 0);
    topBar->setSpacing(ui::Spacing::S);
    topBar->addWidget(logoLabel);
    topBar->addWidget(titleLabel);
    topBar->addStretch(1);
    topBar->addWidget(m_pinButton);
    topBar->addWidget(m_moreButton);
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
    connect(m_inputBar, &InputBar::memoryPanelRequested,
            this, &ChatWindow::openPanelRequested);
    connect(m_inputBar, &InputBar::settingsRequested,
            this, &ChatWindow::settingsRequested);
    connect(m_inputBar, &InputBar::syncPanelRequested,
            this, &ChatWindow::syncPanelRequested);

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
    // 欢迎页放入无边框滚动区：窗口很矮时内容可滚动，英文长文案换行不破坏布局。
    QScrollArea *scroll = new QScrollArea(this);
    scroll->setObjectName(QStringLiteral("welcomeScroll"));
    scroll->setFrameShape(QFrame::NoFrame);
    scroll->setWidgetResizable(true);
    scroll->setHorizontalScrollBarPolicy(Qt::ScrollBarAlwaysOff);
    scroll->setVerticalScrollBarPolicy(Qt::ScrollBarAsNeeded);
    scroll->viewport()->setAutoFillBackground(false);

    QWidget *view = new QWidget(scroll);
    view->setObjectName(QStringLiteral("welcomeView"));
    view->setAccessibleName(tr("PIXIU 欢迎页"));

    QLabel *logo = new QLabel(view);
    const QIcon brandIcon(QStringLiteral(":/icons/pixiu.svg"));
    if (!brandIcon.isNull()) {
        logo->setPixmap(brandIcon.pixmap(QSize(48, 48)));
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

    // 建议问题区域：真实能力对应的问题，点击填入输入框（可编辑后发送）。
    QLabel *suggestLabel = new QLabel(tr("您可以问我："), view);
    suggestLabel->setObjectName(QStringLiteral("suggestLabel"));

    const QStringList suggestions = {
        tr("我们家的水电燃气花了多少钱？"),
        tr("我最近记下了哪些知识点？"),
        tr("我的偏好设置有哪些？"),
        tr("忘记上个月的家庭支出清单"),
    };
    QVBoxLayout *cardsLayout = new QVBoxLayout();
    cardsLayout->setContentsMargins(0, 0, 0, 0);
    cardsLayout->setSpacing(ui::Spacing::S);
    for (const QString &question : suggestions) {
        SuggestionCard *card = new SuggestionCard(question, view);
        connect(card, &QPushButton::clicked, this, [this, question]() {
            if (m_inputBar) {
                m_inputBar->setInputText(question);
            }
        });
        cardsLayout->addWidget(card);
        m_suggestionCards.append(card);
    }

    const QColor iconColor = QApplication::palette().color(QPalette::Mid);
    for (QPushButton *card : m_suggestionCards) {
        if (QLabel *icon = card->findChild<QLabel *>(
                QStringLiteral("suggestionIcon"))) {
            icon->setPixmap(ui::chatIcon(iconColor).pixmap(QSize(14, 14)));
        }
    }
    connect(qApp, &QApplication::paletteChanged, this, [this](const QPalette &) {
        const QColor color = QApplication::palette().color(QPalette::Mid);
        for (QPushButton *card : m_suggestionCards) {
            if (QLabel *icon = card->findChild<QLabel *>(
                    QStringLiteral("suggestionIcon"))) {
                icon->setPixmap(ui::chatIcon(color).pixmap(QSize(14, 14)));
            }
        }
    });

    QLabel *hint = new QLabel(tr("按 Ctrl+Alt+P 随时唤起"), view);
    hint->setObjectName(QStringLiteral("welcomeHint"));
    hint->setAlignment(Qt::AlignCenter);

    QVBoxLayout *layout = new QVBoxLayout(view);
    layout->setContentsMargins(ui::Spacing::M, ui::Spacing::XL,
                               ui::Spacing::M, ui::Spacing::L);
    layout->addWidget(logo);
    layout->addSpacing(ui::Spacing::S);
    layout->addWidget(title);
    layout->addSpacing(ui::Spacing::XS);
    layout->addWidget(subtitle);
    layout->addSpacing(ui::Spacing::L);
    layout->addWidget(suggestLabel);
    layout->addSpacing(ui::Spacing::XS);
    layout->addLayout(cardsLayout);
    layout->addStretch(1);
    layout->addWidget(hint);
    scroll->setWidget(view);
    return scroll;
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
    // 后端状态显示在输入区左下角 badge（InputBar 内部处理文案/颜色/可用性）。
    m_inputBar->setBackendState(state);
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

void ChatWindow::rebuildTopBarIcons()
{
    const QColor color = QApplication::palette().color(QPalette::Text);
    if (m_pinButton) {
        m_pinButton->setIcon(ui::pinIcon(color, m_pinned));
    }
    if (m_moreButton) {
        m_moreButton->setIcon(ui::moreIcon(color));
    }
    if (QPushButton *close = findChild<QPushButton *>(
            QStringLiteral("closeButton"))) {
        close->setIcon(ui::closeIcon(color));
    }
}

void ChatWindow::togglePinned()
{
    m_pinned = !m_pinned;
    setWindowFlag(Qt::WindowStaysOnTopHint, m_pinned);
    show();
    rebuildTopBarIcons();
    m_pinButton->setToolTip(m_pinned ? tr("取消置顶") : tr("置顶"));
    m_pinButton->setAccessibleName(m_pinned ? tr("取消置顶") : tr("置顶聊天框"));
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
