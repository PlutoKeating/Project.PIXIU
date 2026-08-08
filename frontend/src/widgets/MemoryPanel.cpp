#include "widgets/MemoryPanel.h"

#include <QJsonObject>
#include <QLabel>
#include <QListWidget>
#include <QLoggingCategory>
#include <QStringList>
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
    m_tabs->addTab(createConflictTab(), QStringLiteral("冲突"));
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

void MemoryPanel::setConflicts(const QJsonArray &conflicts)
{
    m_conflictList->clear();
    for (const QJsonValue &value : conflicts) {
        const QJsonObject item = value.toObject();

        QStringList lines;
        const QString title = item.value(QStringLiteral("knowledge_title")).toString();
        lines << (title.isEmpty() ? QStringLiteral("（未命名知识）") : title);
        lines << QStringLiteral("字段：%1")
                     .arg(item.value(QStringLiteral("field")).toString());
        lines << QStringLiteral("%1 → %2")
                     .arg(item.value(QStringLiteral("old_value")).toVariant().toString(),
                          item.value(QStringLiteral("new_value")).toVariant().toString());
        lines << QStringLiteral("裁决：%1")
                     .arg(item.value(QStringLiteral("resolution")).toString());

        const QJsonValue timestamp = item.value(QStringLiteral("created_at"));
        if (timestamp.isDouble()) {
            lines << QStringLiteral("时间：%1").arg(qint64(timestamp.toDouble()));
        } else if (timestamp.isString()) {
            lines << QStringLiteral("时间：%1").arg(timestamp.toString());
        }
        m_conflictList->addItem(lines.join(QStringLiteral("\n")));
    }

    const bool hasConflicts = !conflicts.isEmpty();
    m_conflictEmptyLabel->setVisible(!hasConflicts);
    m_conflictList->setVisible(hasConflicts);
}

QWidget *MemoryPanel::createConflictTab()
{
    QWidget *page = new QWidget();
    QVBoxLayout *layout = new QVBoxLayout(page);
    layout->setContentsMargins(8, 8, 8, 8);

    QLabel *titleLabel = new QLabel(QStringLiteral("冲突"), page);
    QFont titleFont = titleLabel->font();
    titleFont.setPixelSize(14);
    titleFont.setBold(true);
    titleLabel->setFont(titleFont);

    m_conflictEmptyLabel = new QLabel(QStringLiteral("暂无冲突记录"), page);
    m_conflictEmptyLabel->setAlignment(Qt::AlignCenter);
    m_conflictList = new QListWidget(page);
    m_conflictList->setWordWrap(true);
    m_conflictList->setVisible(false);

    layout->addWidget(titleLabel);
    layout->addWidget(m_conflictEmptyLabel);
    layout->addWidget(m_conflictList, 1);
    return page;
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
