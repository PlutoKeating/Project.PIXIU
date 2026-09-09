#pragma once
#include <QHBoxLayout>
#include <QVBoxLayout>
#include <QListWidget>
#include <QTabWidget>
#include <QTabBar>
#include <QSignalBlocker>

namespace pixiu {
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
    auto *navigation = new QListWidget(rail);
    navigation->setObjectName("workspaceSections");
    navigation->setAccessibleName(QObject::tr("页面分类"));
    navigation->setFrameShape(QFrame::NoFrame);
    navigation->setHorizontalScrollBarPolicy(Qt::ScrollBarAlwaysOff);
    navigation->setStyleSheet("QListWidget { background: transparent; border: 0; }"
        "QListWidget::item { padding: 12px 8px; margin-bottom: 4px; border-radius: 6px; }"
        "QListWidget::item:selected { background: palette(highlight); color: palette(highlighted-text); }");
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
