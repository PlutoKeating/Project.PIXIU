#include "widgets/FloatingBall.h"

#include "app/UiTokens.h"

#include <QApplication>
#include <QAction>
#include <QContextMenuEvent>
#include <QFont>
#include <QMenu>
#include <QMouseEvent>
#include <QGuiApplication>
#include <QPainter>
#include <QPainterPath>
#include <QScreen>
#include <QString>
#include <QVariantAnimation>

namespace {
int collapsedVisibleWidth()
{
    return qMax(1, static_cast<int>(FloatingBall::kSize * (1.0 / 3.0)));
}
}

FloatingBall::FloatingBall(QWidget *parent)
    : QWidget(parent)
{
    setWindowFlags(Qt::FramelessWindowHint | Qt::WindowStaysOnTopHint | Qt::Tool);
    setAttribute(Qt::WA_TranslucentBackground);
    setFixedSize(kSize, kSize);
    setToolTip(tr("PIXIU 貔貅"));
    buildContextMenu();
}

QSize FloatingBall::sizeHint() const
{
    return QSize(kSize, kSize);
}

int FloatingBall::unreadCount() const
{
    return m_unreadCount;
}

void FloatingBall::setUnreadCount(int count)
{
    const int clamped = qMax(0, count);
    if (m_unreadCount == clamped) {
        return;
    }
    m_unreadCount = clamped;
    if (m_unreadCount > 0) {
        startBadgePulse();
    } else if (m_badgePulseAnim) {
        m_badgePulseAnim->stop();
        m_badgePulse = 1.0;
    }
    update();
}

void FloatingBall::clearUnread()
{
    setUnreadCount(0);
}

void FloatingBall::paintEvent(QPaintEvent *event)
{
    Q_UNUSED(event)

    QPainter painter(this);
    painter.setRenderHint(QPainter::Antialiasing);

    // 半透明圆形主体。
    QPainterPath path;
    path.addEllipse(rect().adjusted(1, 1, -1, -1));
    // 主色跟随主题高亮色（明暗主题下均为系统强调色）。
    QColor accent = QApplication::palette().color(QPalette::Highlight);
    accent.setAlpha(210);
    painter.fillPath(path, accent);

    // 中央 PIXIU 网络标记：三个白色节点 + 互联线段（与 pixiu.svg 图形一致）。
    // 白色在高亮底色上于明暗主题均清晰，无需明暗两套资源。
    const QPointF left(width() * 0.5 - 13, height() * 0.5 - 4);
    const QPointF right(width() * 0.5 + 13, height() * 0.5 - 4);
    const QPointF bottom(width() * 0.5, height() * 0.5 + 11);
    QPen linkPen(Qt::white, 2.4, Qt::SolidLine, Qt::RoundCap, Qt::RoundJoin);
    painter.setPen(linkPen);
    painter.setBrush(Qt::NoBrush);
    painter.drawLine(left, right);
    painter.drawLine(left, bottom);
    painter.drawLine(right, bottom);

    painter.setPen(Qt::NoPen);
    painter.setBrush(Qt::white);
    const qreal nodeRadius = 4.6;
    painter.drawEllipse(left, nodeRadius, nodeRadius);
    painter.drawEllipse(right, nodeRadius, nodeRadius);
    painter.drawEllipse(bottom, nodeRadius, nodeRadius);

    // 未读事件角标：右上角红色圆形 + 数字（超过 99 显示 99+）。
    if (m_unreadCount > 0) {
        const qreal badgeRadius = 10.0 * m_badgePulse;
        const QPointF center(width() - badgeRadius - 2, badgeRadius + 2);
        painter.setPen(Qt::NoPen);
        painter.setBrush(ui::semanticColor(ui::Role::Badge));
        painter.drawEllipse(center, badgeRadius, badgeRadius);

        QFont badgeFont = painter.font();
        badgeFont.setPixelSize(11);
        badgeFont.setBold(true);
        painter.setFont(badgeFont);
        painter.setPen(Qt::white);
        const QString text = m_unreadCount > 99
                                 ? QStringLiteral("99+")
                                 : QString::number(m_unreadCount);
        const QRectF badgeRect(center.x() - badgeRadius, center.y() - badgeRadius,
                               badgeRadius * 2, badgeRadius * 2);
        painter.drawText(badgeRect,
                         Qt::AlignCenter, text);
    }
}

void FloatingBall::startBadgePulse()
{
    if (!m_badgePulseAnim) {
        m_badgePulseAnim = new QVariantAnimation(this);
        connect(m_badgePulseAnim, &QVariantAnimation::valueChanged, this,
                [this](const QVariant &value) {
                    m_badgePulse = value.toReal();
                    update();
                });
        connect(m_badgePulseAnim, &QVariantAnimation::finished, this, [this]() {
            if (m_unreadCount <= 0) {
                m_badgePulse = 1.0;
                update();
                return;
            }
            // 弹入结束后转为持续呼吸（1.0 ↔ 1.06），直到角标清除。
            const qreal current = m_badgePulse;
            m_badgePulseAnim->setDuration(800);
            m_badgePulseAnim->setEasingCurve(QEasingCurve::InOutSine);
            m_badgePulseAnim->setStartValue(current);
            m_badgePulseAnim->setEndValue(current <= 1.03 ? 1.06 : 1.0);
            m_badgePulseAnim->start();
        });
    }
    m_badgePulseAnim->stop();
    m_badgePulse = 1.45;
    m_badgePulseAnim->setDuration(180);
    m_badgePulseAnim->setEasingCurve(QEasingCurve::OutBack);
    m_badgePulseAnim->setStartValue(1.45);
    m_badgePulseAnim->setEndValue(1.0);
    m_badgePulseAnim->start();
}

void FloatingBall::mousePressEvent(QMouseEvent *event)
{
    if (event->button() == Qt::LeftButton) {
        m_dragOffset = event->globalPos() - frameGeometry().topLeft();
        m_pressGlobalPos = event->globalPos();
        m_wasDrag = false;
        event->accept();
    } else {
        QWidget::mousePressEvent(event);
    }
}

void FloatingBall::mouseMoveEvent(QMouseEvent *event)
{
    if (event->buttons() & Qt::LeftButton) {
        move(event->globalPos() - m_dragOffset);
        if ((event->globalPos() - m_pressGlobalPos).manhattanLength() > kDragThresholdPx) {
            m_wasDrag = true;
        }
        event->accept();
    } else {
        QWidget::mouseMoveEvent(event);
    }
}

void FloatingBall::mouseReleaseEvent(QMouseEvent *event)
{
    if (event->button() == Qt::LeftButton) {
        if (!m_wasDrag) {
            emit clicked();
        } else {
            m_expandedPos = frameGeometry().topLeft();
            snapToEdge();
            emit movedTo(frameGeometry().topLeft());
        }
        event->accept();
    } else {
        QWidget::mouseReleaseEvent(event);
    }
}

void FloatingBall::enterEvent(QEvent *event)
{
    if (m_collapsed) {
        expandFromEdge();
    }
    QWidget::enterEvent(event);
}

void FloatingBall::leaveEvent(QEvent *event)
{
    if (!m_collapsed) {
        snapToEdge();
    }
    QWidget::leaveEvent(event);
}

void FloatingBall::contextMenuEvent(QContextMenuEvent *event)
{
    if (m_contextMenu) {
        m_contextMenu->popup(event->globalPos());
        event->accept();
        return;
    }
    QWidget::contextMenuEvent(event);
}

void FloatingBall::buildContextMenu()
{
    m_contextMenu = new QMenu(this);

    QAction *toggleAction = m_contextMenu->addAction(tr("打开聊天框"));
    toggleAction->setObjectName(QStringLiteral("toggleChatAction"));
    // “打开聊天框”语义与左键单击一致（统一走 toggleChatWindow）。
    connect(toggleAction, &QAction::triggered, this, &FloatingBall::clicked);

    QAction *panelAction = m_contextMenu->addAction(tr("记忆面板"));
    panelAction->setObjectName(QStringLiteral("openPanelAction"));
    connect(panelAction, &QAction::triggered, this, &FloatingBall::openPanelRequested);

    QAction *settingsAction = m_contextMenu->addAction(tr("设置"));
    settingsAction->setObjectName(QStringLiteral("settingsAction"));
    connect(settingsAction, &QAction::triggered, this, &FloatingBall::settingsRequested);

    m_contextMenu->addSeparator();

    QAction *quitAction = m_contextMenu->addAction(tr("退出"));
    quitAction->setObjectName(QStringLiteral("quitAction"));
    connect(quitAction, &QAction::triggered, this, &FloatingBall::quitRequested);
}

void FloatingBall::restorePosition(const QPoint &savedPos)
{
    QScreen *screen = screenFor(savedPos);
    if (!screen) {
        screen = QGuiApplication::primaryScreen();
    }
    if (!screen) {
        move(savedPos);
        m_expandedPos = savedPos;
        return;
    }

    const QRect area = screen->availableGeometry();
    const int x = qBound(area.left(), savedPos.x(), area.right() - width() + 1);
    const int y = qBound(area.top(), savedPos.y(), area.bottom() - height() + 1);
    const QPoint clamped(x, y);

    m_expandedPos = clamped;
    move(clamped);
    snapToEdge();
    emit movedTo(frameGeometry().topLeft());
}

QScreen *FloatingBall::screenFor(const QPoint &globalPos) const
{
    return QGuiApplication::screenAt(globalPos);
}

void FloatingBall::snapToEdge()
{
    QScreen *screen = screenFor(m_expandedPos);
    if (!screen) {
        screen = QGuiApplication::primaryScreen();
    }
    if (!screen) {
        return;
    }

    const QRect area = screen->availableGeometry();
    const bool nearLeft = m_expandedPos.x() <= area.left() + kEdgeSnapPx;
    const bool nearRight = m_expandedPos.x() + width() >= area.right() - kEdgeSnapPx;

    if (nearLeft || nearRight) {
        collapseToEdge();
    }
}

void FloatingBall::collapseToEdge()
{
    QScreen *screen = screenFor(m_expandedPos);
    if (!screen) {
        screen = QGuiApplication::primaryScreen();
    }
    if (!screen) {
        return;
    }

    const QRect area = screen->availableGeometry();
    const int visible = collapsedVisibleWidth();
    const bool atLeft = m_expandedPos.x() <= area.left() + kEdgeSnapPx;
    const int x = atLeft
                      ? area.left() - width() + visible
                      : area.right() - visible + 1;

    m_collapsed = true;
    move(x, m_expandedPos.y());
}

void FloatingBall::expandFromEdge()
{
    m_collapsed = false;
    move(m_expandedPos);
    emit movedTo(m_expandedPos);
}
