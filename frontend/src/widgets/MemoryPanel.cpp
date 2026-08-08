#include "widgets/MemoryPanel.h"

#include <QHBoxLayout>
#include <QJsonDocument>
#include <QJsonObject>
#include <QKeyEvent>
#include <QLabel>
#include <QLineEdit>
#include <QListWidget>
#include <QLoggingCategory>
#include <QPushButton>
#include <QStringList>
#include <QTabWidget>
#include <QVBoxLayout>

Q_LOGGING_CATEGORY(lcPanel, "pixiu.memory-panel")

MemoryPanel::MemoryPanel(QWidget *parent)
    : QWidget(parent)
{
    setWindowTitle(tr("记忆管理"));
    setFixedSize(520, 420);

    m_tabs = new QTabWidget(this);
    m_tabs->addTab(createPreferenceTab(), tr("偏好"));
    m_tabs->addTab(createConflictTab(), tr("冲突"));
    m_tabs->addTab(createPlaceholderTab(
                       tr("同步"),
                       tr("节点列表与设备配对（Phase 6）")),
                   tr("同步"));

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

void MemoryPanel::keyPressEvent(QKeyEvent *event)
{
    if (event->key() == Qt::Key_Escape) {
        hide();
        event->accept();
        return;
    }
    QWidget::keyPressEvent(event);
}

void MemoryPanel::setConflicts(const QJsonArray &conflicts)
{
    m_conflictList->clear();
    for (const QJsonValue &value : conflicts) {
        const QJsonObject item = value.toObject();

        QStringList lines;
        const QString title = item.value(QStringLiteral("knowledge_title")).toString();
        lines << (title.isEmpty() ? tr("（未命名知识）") : title);
        lines << tr("字段：%1")
                     .arg(item.value(QStringLiteral("field")).toString());
        lines << tr("%1 → %2")
                     .arg(item.value(QStringLiteral("old_value")).toVariant().toString(),
                          item.value(QStringLiteral("new_value")).toVariant().toString());
        lines << tr("裁决：%1")
                     .arg(item.value(QStringLiteral("resolution")).toString());

        const QJsonValue timestamp = item.value(QStringLiteral("created_at"));
        if (timestamp.isDouble()) {
            lines << tr("时间：%1").arg(qint64(timestamp.toDouble()));
        } else if (timestamp.isString()) {
            lines << tr("时间：%1").arg(timestamp.toString());
        }
        m_conflictList->addItem(lines.join(QStringLiteral("\n")));
    }

    const bool hasConflicts = !conflicts.isEmpty();
    m_conflictEmptyLabel->setVisible(!hasConflicts);
    m_conflictList->setVisible(hasConflicts);
}

void MemoryPanel::setPreferenceHistory(const QJsonObject &response)
{
    const QString key = response.value(QStringLiteral("key")).toString();
    const int currentVersion =
        response.value(QStringLiteral("current_version")).toInt();
    m_prefHeaderLabel->setText(
        key.isEmpty()
            ? tr("偏好历史")
            : tr("%1 · v%2").arg(key).arg(currentVersion));

    m_prefHistoryList->clear();
    const QJsonArray history = response.value(QStringLiteral("history")).toArray();
    for (const QJsonValue &value : history) {
        const QJsonObject snapshot = value.toObject();

        QStringList line;
        line << tr("v%1").arg(snapshot.value(QStringLiteral("version")).toInt());
        const QJsonValue updated = snapshot.value(QStringLiteral("updated_at"));
        if (updated.isDouble()) {
            line << tr("时间 %1").arg(qint64(updated.toDouble()));
        } else if (updated.isString()) {
            line << tr("时间 %1").arg(updated.toString());
        }
        const QByteArray valueJson =
            QJsonDocument(snapshot.value(QStringLiteral("value")).toObject())
                .toJson(QJsonDocument::Compact);
        line << QString::fromUtf8(valueJson);

        m_prefHistoryList->addItem(line.join(QStringLiteral(" · ")));
    }

    const bool hasHistory = !history.isEmpty();
    m_prefEmptyLabel->setVisible(!hasHistory);
    m_prefHistoryList->setVisible(hasHistory);
}

QWidget *MemoryPanel::createPreferenceTab()
{
    QWidget *page = new QWidget();
    QVBoxLayout *layout = new QVBoxLayout(page);
    layout->setContentsMargins(8, 8, 8, 8);

    m_prefHeaderLabel = new QLabel(tr("偏好历史"), page);
    QFont headerFont = m_prefHeaderLabel->font();
    headerFont.setPixelSize(14);
    headerFont.setBold(true);
    m_prefHeaderLabel->setFont(headerFont);

    m_prefIdInput = new QLineEdit(page);
    m_prefIdInput->setPlaceholderText(tr("偏好 ID（如 pref_…）"));
    QPushButton *loadButton = new QPushButton(tr("加载历史"), page);
    connect(loadButton, &QPushButton::clicked, this, [this]() {
        emit historyRequested(m_prefIdInput->text().trimmed());
    });
    connect(m_prefIdInput, &QLineEdit::returnPressed, this, [this]() {
        emit historyRequested(m_prefIdInput->text().trimmed());
    });

    QHBoxLayout *inputRow = new QHBoxLayout();
    inputRow->addWidget(m_prefIdInput, 1);
    inputRow->addWidget(loadButton);

    m_prefEmptyLabel = new QLabel(tr("暂无历史记录"), page);
    m_prefEmptyLabel->setAlignment(Qt::AlignCenter);
    m_prefHistoryList = new QListWidget(page);
    m_prefHistoryList->setObjectName(QStringLiteral("prefHistoryList"));
    m_prefHistoryList->setVisible(false);

    layout->addWidget(m_prefHeaderLabel);
    layout->addLayout(inputRow);
    layout->addWidget(m_prefEmptyLabel);
    layout->addWidget(m_prefHistoryList, 1);
    return page;
}

QWidget *MemoryPanel::createConflictTab()
{
    QWidget *page = new QWidget();
    QVBoxLayout *layout = new QVBoxLayout(page);
    layout->setContentsMargins(8, 8, 8, 8);

    QLabel *titleLabel = new QLabel(tr("冲突"), page);
    QFont titleFont = titleLabel->font();
    titleFont.setPixelSize(14);
    titleFont.setBold(true);
    titleLabel->setFont(titleFont);

    m_conflictEmptyLabel = new QLabel(tr("暂无冲突记录"), page);
    m_conflictEmptyLabel->setAlignment(Qt::AlignCenter);
    m_conflictList = new QListWidget(page);
    m_conflictList->setObjectName(QStringLiteral("conflictList"));
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
