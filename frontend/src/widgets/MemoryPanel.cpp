#include "widgets/MemoryPanel.h"

#include "widgets/PairDialog.h"
#include "widgets/RevokeDialog.h"

#include <QCoreApplication>
#include <QDateTime>
#include <QFont>
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

namespace {
QString formatTimestamp(qint64 ts)
{
    return QDateTime::fromSecsSinceEpoch(ts).toString(QStringLiteral("HH:mm"));
}

QString peerStateText(bool isSelf, const QString &state)
{
    if (isSelf) {
        return QCoreApplication::translate("MemoryPanel", "本机");
    }
    if (state == QStringLiteral("ONLINE")) {
        return QCoreApplication::translate("MemoryPanel", "在线");
    }
    if (state == QStringLiteral("OFFLINE")) {
        return QCoreApplication::translate("MemoryPanel", "离线");
    }
    return state.isEmpty()
               ? QCoreApplication::translate("MemoryPanel", "状态未知")
               : state;
}
}

MemoryPanel::MemoryPanel(QWidget *parent)
    : QWidget(parent)
{
    setWindowTitle(tr("记忆管理"));
    setFixedSize(520, 420);

    m_tabs = new QTabWidget(this);
    m_tabs->addTab(createPreferenceTab(), tr("偏好"));
    m_tabs->addTab(createConflictTab(), tr("冲突"));
    m_tabs->addTab(createSyncTab(), tr("同步"));

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

void MemoryPanel::showConflictTab()
{
    if (m_tabs) {
        m_tabs->setCurrentIndex(1);
    }
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

void MemoryPanel::setSyncStatus(const QString &status, bool ok)
{
    if (!m_syncStatusLabel) {
        return;
    }
    m_syncStatusLabel->setText(status);
    m_syncStatusLabel->setStyleSheet(
        ok ? QStringLiteral("color: #1a7f37;")
           : QStringLiteral("color: #d93025;"));
    m_syncStatusLabel->show();
}

void MemoryPanel::setPeers(const QJsonArray &peers)
{
    m_peerList->clear();

    for (const QJsonValue &value : peers) {
        const QJsonObject peer = value.toObject();
        const QString id = peer.value(QStringLiteral("id")).toString();
        const QString name = peer.value(QStringLiteral("name")).toString();
        const bool isSelf = peer.value(QStringLiteral("is_self")).toBool(false);
        const QString state = peer.value(QStringLiteral("status")).toString();

        QWidget *container = new QWidget();
        QVBoxLayout *layout = new QVBoxLayout(container);
        layout->setContentsMargins(4, 4, 4, 4);
        layout->setSpacing(2);

        QHBoxLayout *nameRow = new QHBoxLayout();
        QLabel *nameLabel = new QLabel(
            name.isEmpty() ? tr("（未命名设备）") : name, container);
        QFont nameFont = nameLabel->font();
        nameFont.setBold(true);
        nameLabel->setFont(nameFont);

        QLabel *stateLabel = new QLabel(peerStateText(isSelf, state), container);
        if (isSelf || state == QStringLiteral("ONLINE")) {
            stateLabel->setStyleSheet(
                QStringLiteral("color: #1a7f37; font-size: 11px;"));
        } else if (state == QStringLiteral("OFFLINE")) {
            stateLabel->setStyleSheet(
                QStringLiteral("color: #9aa0a6; font-size: 11px;"));
        }

        nameRow->addWidget(nameLabel);
        nameRow->addStretch(1);
        nameRow->addWidget(stateLabel);
        layout->addLayout(nameRow);

        QStringList meta;
        const QJsonValue lastSync = peer.value(QStringLiteral("last_sync_ts"));
        if (lastSync.isDouble()) {
            meta << tr("上次同步 %1").arg(formatTimestamp(qint64(lastSync.toDouble())));
        } else if (lastSync.isString()) {
            meta << tr("上次同步 %1").arg(lastSync.toString());
        }
        if (peer.contains(QStringLiteral("pending_ops"))) {
            meta << tr("待同步 %1 条")
                        .arg(peer.value(QStringLiteral("pending_ops")).toInt(0));
        }
        if (!meta.isEmpty()) {
            QLabel *metaLabel = new QLabel(meta.join(QStringLiteral(" · ")), container);
            metaLabel->setStyleSheet(
                QStringLiteral("color: #9aa0a6; font-size: 11px;"));
            layout->addWidget(metaLabel);
        }

        // 本机不可解绑；其他设备提供“解绑”入口（二次确认在应用层触发）。
        if (!isSelf) {
            QPushButton *revokeButton = new QPushButton(tr("解绑"), container);
            revokeButton->setObjectName(QStringLiteral("revokeButton"));
            revokeButton->setAccessibleName(tr("解绑设备 %1").arg(name));
            revokeButton->setCursor(Qt::PointingHandCursor);
            revokeButton->setFlat(true);
            connect(revokeButton, &QPushButton::clicked, this,
                    [this, id, name]() { requestRevoke(id, name); });

            QHBoxLayout *buttonRow = new QHBoxLayout();
            buttonRow->addStretch(1);
            buttonRow->addWidget(revokeButton);
            layout->addLayout(buttonRow);
        }

        QListWidgetItem *item = new QListWidgetItem(m_peerList);
        item->setFlags(Qt::ItemIsEnabled);
        item->setSizeHint(container->sizeHint());
        m_peerList->setItemWidget(item, container);
    }

    const bool hasPeers = !peers.isEmpty();
    m_peerList->setVisible(hasPeers);
    m_syncEmptyLabel->setVisible(!hasPeers);
}

void MemoryPanel::setSyncSummary(const QJsonObject &status)
{
    QStringList parts;
    const QString domain = status.value(QStringLiteral("domain")).toString();
    if (!domain.isEmpty()) {
        parts << tr("共享域 %1").arg(domain);
    }
    const int online = status.value(QStringLiteral("peers_online")).toInt(-1);
    const int total = status.value(QStringLiteral("peers_total")).toInt(-1);
    if (online >= 0 && total >= 0) {
        parts << tr("在线 %1/%2").arg(online).arg(total);
    }
    if (status.contains(QStringLiteral("pending_outgoing_ops"))) {
        parts << tr("待同步 %1 条")
                     .arg(status.value(QStringLiteral("pending_outgoing_ops")).toInt(0));
    }
    const QJsonValue antiEntropy = status.value(QStringLiteral("last_anti_entropy_ts"));
    if (antiEntropy.isDouble()) {
        parts << tr("上次对账 %1")
                     .arg(formatTimestamp(qint64(antiEntropy.toDouble())));
    } else if (antiEntropy.isString()) {
        parts << tr("上次对账 %1").arg(antiEntropy.toString());
    }
    if (status.contains(QStringLiteral("total_ops_synced"))) {
        parts << tr("累计同步 %1 条")
                     .arg(status.value(QStringLiteral("total_ops_synced")).toInt(0));
    }

    m_syncSummaryLabel->setText(parts.join(QStringLiteral(" · ")));
    m_syncSummaryLabel->setVisible(!parts.isEmpty());
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

QWidget *MemoryPanel::createSyncTab()
{
    QWidget *page = new QWidget();
    QVBoxLayout *layout = new QVBoxLayout(page);
    layout->setContentsMargins(8, 8, 8, 8);

    QLabel *titleLabel = new QLabel(tr("同步"), page);
    QFont titleFont = titleLabel->font();
    titleFont.setPixelSize(14);
    titleFont.setBold(true);
    titleLabel->setFont(titleFont);

    m_syncStatusLabel = new QLabel(
        tr("正在加载同步状态…"), page);
    m_syncStatusLabel->setObjectName(QStringLiteral("syncStatusLabel"));
    m_syncStatusLabel->setWordWrap(true);
    m_syncStatusLabel->setStyleSheet(
        QStringLiteral("color: #9aa0a6; font-size: 11px;"));

    QLabel *descLabel = new QLabel(
        tr("配对后设备加入共享域，记忆经后端 CRDT 跨设备同步。"), page);
    descLabel->setWordWrap(true);

    m_syncSummaryLabel = new QLabel(page);
    m_syncSummaryLabel->setObjectName(QStringLiteral("syncSummaryLabel"));
    m_syncSummaryLabel->setWordWrap(true);
    m_syncSummaryLabel->setVisible(false);

    m_syncEmptyLabel = new QLabel(tr("暂无节点"), page);
    m_syncEmptyLabel->setObjectName(QStringLiteral("syncEmptyLabel"));
    m_syncEmptyLabel->setAlignment(Qt::AlignCenter);

    m_peerList = new QListWidget(page);
    m_peerList->setObjectName(QStringLiteral("peerList"));
    m_peerList->setVisible(false);

    QPushButton *pairButton = new QPushButton(tr("配对设备"), page);
    pairButton->setObjectName(QStringLiteral("pairDeviceButton"));
    pairButton->setAccessibleName(tr("打开设备配对"));
    connect(pairButton, &QPushButton::clicked, this, [this]() {
        if (!m_pairDialog) {
            m_pairDialog = new PairDialog(this);
            connect(m_pairDialog, &PairDialog::pairRequested,
                    this, &MemoryPanel::pairRequested);
        }
        m_pairDialog->showAndFocus();
    });

    QPushButton *refreshButton = new QPushButton(tr("刷新"), page);
    refreshButton->setObjectName(QStringLiteral("syncRefreshButton"));
    refreshButton->setAccessibleName(tr("刷新节点与同步状态"));
    connect(refreshButton, &QPushButton::clicked, this, [this]() {
        m_syncStatusLabel->setText(tr("正在加载同步状态…"));
        m_syncStatusLabel->setStyleSheet(
            QStringLiteral("color: #9aa0a6; font-size: 11px;"));
        m_syncStatusLabel->show();
        emit syncRefreshRequested();
    });

    QHBoxLayout *buttonRow = new QHBoxLayout();
    buttonRow->addWidget(pairButton);
    buttonRow->addWidget(refreshButton);
    buttonRow->addStretch(1);

    layout->addWidget(titleLabel);
    layout->addWidget(m_syncStatusLabel);
    layout->addWidget(descLabel);
    layout->addWidget(m_syncSummaryLabel);
    layout->addWidget(m_syncEmptyLabel);
    layout->addWidget(m_peerList, 1);
    layout->addLayout(buttonRow);
    return page;
}

void MemoryPanel::requestRevoke(const QString &peerId, const QString &peerName)
{
    if (!m_revokeDialog) {
        m_revokeDialog = new RevokeDialog(this);
        connect(m_revokeDialog, &RevokeDialog::confirmed, this, [this]() {
            const QString id = m_pendingRevokePeerId;
            m_pendingRevokePeerId.clear();
            if (!id.isEmpty()) {
                emit revokeConfirmed(id);
            }
        });
        connect(m_revokeDialog, &RevokeDialog::cancelled, this, [this]() {
            m_pendingRevokePeerId.clear();
        });
    }
    m_pendingRevokePeerId = peerId;
    m_revokeDialog->setPeerName(peerName);
    m_revokeDialog->showAndFocus();
}
