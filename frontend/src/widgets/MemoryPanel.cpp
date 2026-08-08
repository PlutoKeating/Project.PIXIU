#include "widgets/MemoryPanel.h"

#include <QLabel>
#include <QLoggingCategory>
#include <QTabWidget>
#include <QVBoxLayout>

Q_LOGGING_CATEGORY(lcPanel, "pixiu.memory-panel")

MemoryPanel::MemoryPanel(QWidget *parent)
    : QWidget(parent)
{
    setWindowTitle(QStringLiteral("记忆管理"));
    setFixedSize(520, 420);

    m_tabs = new QTabWidget(this);
    m_tabs->addTab(createPlaceholderTab(
                       QStringLiteral("偏好"),
                       QStringLiteral("偏好历史与版本回溯（Phase 5.2）")),
                   QStringLiteral("偏好"));
    m_tabs->addTab(createPlaceholderTab(
                       QStringLiteral("冲突"),
                       QStringLiteral("冲突审计 old/new 对比（Phase 5.3）")),
                   QStringLiteral("冲突"));
    m_tabs->addTab(createPlaceholderTab(
                       QStringLiteral("同步"),
                       QStringLiteral("节点列表与设备配对（Phase 6）")),
                   QStringLiteral("同步"));

    QVBoxLayout *layout = new QVBoxLayout(this);
    layout->setContentsMargins(8, 8, 8, 8);
    layout->addWidget(m_tabs);
}

void MemoryPanel::showAndFocus()
{
    show();
    raise();
    activateWindow();
}

QWidget *MemoryPanel::createPlaceholderTab(const QString &title,
                                           const QString &description) const
{
    QWidget *page = new QWidget();
    QLabel *titleLabel = new QLabel(title, page);
    QFont font = titleLabel->font();
    font.setPixelSize(14);
    font.setBold(true);
    titleLabel->setFont(font);

    QLabel *descLabel = new QLabel(description, page);
    descLabel->setWordWrap(true);

    QVBoxLayout *layout = new QVBoxLayout(page);
    layout->addWidget(titleLabel);
    layout->addWidget(descLabel);
    layout->addStretch(1);
    return page;
}
