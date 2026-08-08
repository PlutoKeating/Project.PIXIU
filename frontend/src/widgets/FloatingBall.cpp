#include "widgets/FloatingBall.h"

#include <QFont>
#include <QMouseEvent>
#include <QGuiApplication>
#include <QPainter>
#include <QPainterPath>
#include <QScreen>
#include <QString>

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
    setToolTip(QStringLiteral("PIXIU 貔貅"));
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
    painter.fillPath(path, QColor(0x35, 0x87, 0xF6, 210));

    // 中央字符（后续替换为资源图标）。
    QFont font = painter.font();
    font.setPixelSize(24);
    font.setBold(true);
    painter.setFont(font);
    painter.setPen(Qt::white);
    painter.drawText(rect(), Qt::AlignCenter, QStringLiteral("貔"));

    // 未读事件角标：右上角红色圆形 + 数字（超过 99 显示 99+）。
    if (m_unreadCount > 0) {
        const int badgeRadius = 10;
        const QPointF center(width() - badgeRadius - 2, badgeRadius + 2);
        painter.setPen(Qt::NoPen);
        painter.setBrush(QColor(0xD9, 0x30, 0x25));
        painter.drawEllipse(center, badgeRadius, badgeRadius);

        QFont badgeFont = font;
        badgeFont.setPixelSize(11);
        badgeFont.setBold(true);
        painter.setFont(badgeFont);
        painter.setPen(Qt::white);
        const QString text = m_unreadCount > 99
                                 ? QStringLiteral("99+")
                                 : QString::number(m_unreadCount);
        painter.drawText(QRectF(center.x() - badgeRadius, center.y() - badgeRadius,
                                badgeRadius * 2, badgeRadius * 2),
                         Qt::AlignCenter, text);
    }
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
