#pragma once
#include "MotionPreferences.h"
#include <QDynamicPropertyChangeEvent>
#include <QHBoxLayout>
#include <QVBoxLayout>
#include <QListWidget>
#include <QTabWidget>
#include <QTabBar>
#include <QSignalBlocker>
#include <QVariantAnimation>
#include <QPainter>
#include <QApplication>
#include <QStyle>
#include <QResizeEvent>
#include <QShowEvent>

namespace pixiu {
class WorkspaceSectionList final : public QListWidget {
public:
    explicit WorkspaceSectionList(QWidget *parent = nullptr) : QListWidget(parent), m_motion(this)
    {
        MotionPreferences::enabled();
        qApp->installEventFilter(this);
        m_motion.setDuration(160);
        m_motion.setEasingCurve(QEasingCurve::OutCubic);
        connect(&m_motion, &QVariantAnimation::valueChanged, this, [this](const QVariant &value) {
            m_indicator = value.toRectF();
            viewport()->update();
        });
    }
protected:
    bool eventFilter(QObject *watched, QEvent *event) override
    {
        if (watched == qApp && event->type() == QEvent::DynamicPropertyChange
            && static_cast<QDynamicPropertyChangeEvent *>(event)->propertyName() == MotionPreferences::propertyName)
            moveIndicator(false);
        return QListWidget::eventFilter(watched, event);
    }
    void currentChanged(const QModelIndex &current, const QModelIndex &previous) override
    {
        QListWidget::currentChanged(current, previous);
        moveIndicator(isVisible());
    }
    void resizeEvent(QResizeEvent *event) override
    {
        QListWidget::resizeEvent(event);
        moveIndicator(false);
    }
    void showEvent(QShowEvent *event) override
    {
        QListWidget::showEvent(event);
        moveIndicator(false);
    }
    void paintEvent(QPaintEvent *event) override
    {
        QListWidget::paintEvent(event);
        if (m_indicator.isEmpty()) return;
        QPainter painter(viewport());
        painter.setRenderHint(QPainter::Antialiasing);
        auto tint = palette().color(QPalette::Highlight);
        tint.setAlpha(28);
        painter.setPen(Qt::NoPen);
        painter.setBrush(tint);
        painter.drawRoundedRect(m_indicator, 6, 6);
        painter.setBrush(palette().color(QPalette::Highlight));
        painter.drawRoundedRect(QRectF(m_indicator.left(), m_indicator.top() + 10,
                                      3, qMax(0.0, m_indicator.height() - 20)), 1.5, 1.5);
    }
private:
    void moveIndicator(bool animate)
    {
        const QRectF target = currentItem()
            ? QRectF(visualItemRect(currentItem()).adjusted(0, 0, -1, -4)) : QRectF();
        m_motion.stop(); // Restart from the currently painted position, never queue transitions.
        const bool enabled = MotionPreferences::enabled() && QApplication::isEffectEnabled(Qt::UI_AnimateMenu)
            && style()->styleHint(QStyle::SH_Widget_Animation_Duration, nullptr, this) > 0;
        if (!animate || !enabled || m_indicator.isEmpty() || target.isEmpty()) {
            m_indicator = target;
            viewport()->update();
            return;
        }
        m_motion.setStartValue(m_indicator);
        m_motion.setEndValue(target);
        m_motion.start();
    }
    QVariantAnimation m_motion;
    QRectF m_indicator;
};

// Keep page ownership and programmatic navigation in QTabWidget; present a
// horizontal-text desktop sidebar instead of a rotated vertical tab bar.
inline void installWorkspaceNavigation(QVBoxLayout *outer, QTabWidget *tabs,
                                       const QStringList &labels, QWidget *footer = nullptr)
{
    outer->removeWidget(tabs);
    tabs->tabBar()->hide();
    auto *row = new QHBoxLayout;
    row->setSpacing(0);
    auto *rail = new QWidget(tabs->parentWidget());
    rail->setFixedWidth(160);
    auto *navigationLayout = new QVBoxLayout(rail);
    navigationLayout->setContentsMargins(12, 24, 12, 20);
    auto *navigation = new WorkspaceSectionList(rail);
    navigation->setObjectName("workspaceSections");
    navigation->setAccessibleName(QObject::tr("页面分类"));
    navigation->setFrameShape(QFrame::NoFrame);
    navigation->setHorizontalScrollBarPolicy(Qt::ScrollBarAlwaysOff);
    navigation->setStyleSheet("QListWidget { background: transparent; border: 0; }"
        "QListWidget::item { padding: 12px 8px; margin-bottom: 4px; border-radius: 6px; }"
        "QListWidget::item:selected { background: transparent; color: palette(text); }");
    navigation->addItems(labels);
    navigation->setCurrentRow(tabs->currentIndex());
    navigationLayout->addWidget(navigation, 1);
    if (footer) navigationLayout->addWidget(footer);
    row->addWidget(rail);
    row->addWidget(tabs, 1);
    outer->addLayout(row);
    QObject::connect(navigation, &QListWidget::currentRowChanged, tabs, &QTabWidget::setCurrentIndex);
    QObject::connect(tabs, &QTabWidget::currentChanged, navigation, [navigation, labels](int index) {
        const QSignalBlocker blocker(navigation);
        navigation->setCurrentRow(index < labels.size() ? index : -1);
    });
}
}
