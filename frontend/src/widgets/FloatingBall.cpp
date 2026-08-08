#include "widgets/FloatingBall.h"

#include <QMouseEvent>
#include <QPainter>
#include <QPainterPath>

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
            emit movedTo(frameGeometry().topLeft());
        }
        event->accept();
    } else {
        QWidget::mouseReleaseEvent(event);
    }
}
