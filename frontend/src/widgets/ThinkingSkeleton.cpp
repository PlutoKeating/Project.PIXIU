#include "widgets/ThinkingSkeleton.h"

#include <QApplication>
#include <QEasingCurve>
#include <QPainter>
#include <QPalette>
#include <QVariantAnimation>

namespace {
constexpr int kHeight = 64;
constexpr qreal kMinAlpha = 0.45;
constexpr qreal kMaxAlpha = 0.9;
}

ThinkingSkeleton::ThinkingSkeleton(QWidget *parent)
    : QWidget(parent)
{
    setObjectName(QStringLiteral("thinkingSkeleton"));
    setFixedHeight(kHeight);

    // 呼吸脉冲：正向淡入淡出后自动反向，形成连续循环（快、轻、可中断）。
    m_pulse = new QVariantAnimation(this);
    m_pulse->setStartValue(kMinAlpha);
    m_pulse->setEndValue(kMaxAlpha);
    m_pulse->setDuration(700);
    m_pulse->setEasingCurve(QEasingCurve::InOutSine);
    connect(m_pulse, &QVariantAnimation::valueChanged, this,
            [this](const QVariant &value) {
                m_alpha = value.toReal();
                update();
            });
    connect(m_pulse, &QVariantAnimation::finished, this, [this]() {
        const qreal current = m_alpha;
        m_pulse->setStartValue(current);
        m_pulse->setEndValue(current > (kMinAlpha + kMaxAlpha) / 2.0
                                 ? kMinAlpha
                                 : kMaxAlpha);
        m_pulse->start();
    });
    m_pulse->start();
}

QSize ThinkingSkeleton::sizeHint() const
{
    return QSize(300, kHeight);
}

void ThinkingSkeleton::paintEvent(QPaintEvent *event)
{
    Q_UNUSED(event)

    QPainter painter(this);
    painter.setRenderHint(QPainter::Antialiasing);
    painter.setPen(Qt::NoPen);

    QColor bar = QApplication::palette().color(QPalette::Mid);
    bar.setAlphaF(m_alpha);
    painter.setBrush(bar);

    const qreal radius = 6.0;
    const qreal width = this->width() - 48.0;
    const QRectF bars[] = {
        QRectF(24, 6, width, 12),
        QRectF(24, 26, width * 0.84, 12),
        QRectF(24, 46, width * 0.62, 12),
    };
    for (const QRectF &rect : bars) {
        painter.drawRoundedRect(rect, radius, radius);
    }
}
