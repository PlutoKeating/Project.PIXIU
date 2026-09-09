#pragma once
#include "MotionPreferences.h"
#include <QDynamicPropertyChangeEvent>
#include <QGraphicsOpacityEffect>
#include <QPropertyAnimation>
#include <QWidget>
#include <QStyle>

namespace pixiu {
// Animate appearance only: content geometry, input and visibility remain owned
// by the page. Repeated data updates never restart an already visible report.
class ContentReveal final : public QObject {
public:
    explicit ContentReveal(QWidget *target) : QObject(target), m_target(target), m_motion(this)
    {
        MotionPreferences::enabled();
        m_effect = new QGraphicsOpacityEffect(target);
        m_effect->setOpacity(1);
        target->setGraphicsEffect(m_effect);
        m_motion.setTargetObject(m_effect);
        m_motion.setPropertyName("opacity");
        m_motion.setDuration(160);
        m_motion.setEasingCurve(QEasingCurve::OutCubic);
        target->installEventFilter(this);
        qApp->installEventFilter(this);
    }
protected:
    bool eventFilter(QObject *watched, QEvent *event) override
    {
        if (watched == m_target && event->type() == QEvent::Show) {
            settle();
            if (MotionPreferences::enabled() && QApplication::isEffectEnabled(Qt::UI_AnimateMenu)
                && m_target->style()->styleHint(QStyle::SH_Widget_Animation_Duration) > 0) {
                m_motion.setStartValue(0.65);
                m_motion.setEndValue(1.0);
                m_motion.start();
            }
        } else if ((watched == m_target && event->type() == QEvent::Hide)
            || (watched == qApp && event->type() == QEvent::DynamicPropertyChange
                && static_cast<QDynamicPropertyChangeEvent *>(event)->propertyName() == MotionPreferences::propertyName)) {
            settle();
        }
        return QObject::eventFilter(watched, event);
    }
private:
    void settle() { m_motion.stop(); m_effect->setOpacity(1); }
    QWidget *m_target;
    QGraphicsOpacityEffect *m_effect;
    QPropertyAnimation m_motion;
};
}
