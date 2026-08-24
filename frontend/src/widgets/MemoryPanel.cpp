#include "widgets/MemoryPanel.h"

#include "app/UiTokens.h"
#include "widgets/PairDialog.h"
#include "widgets/RevokeDialog.h"

#include <QCoreApplication>
#include <QComboBox>
#include <QDateTime>
#include <QFontMetrics>
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

QString elidePeerName(const QFont &font, const QString &name, int maxWidth)
{
    return QFontMetrics(font).elidedText(name, Qt::ElideRight, maxWidth);
}
}

MemoryPanel::MemoryPanel(QWidget *parent)
    : QWidget(parent)
{
    setWindowTitle(tr("记忆管理"));
    resize(560, 480);
    setMinimumSize(480, 400);

    m_tabs = new QTabWidget(this);
    m_tabs->addTab(createPreferenceTab(), tr("偏好"));
    m_tabs->addTab(createConflictTab(), tr("冲突"));
    m_tabs->addTab(createSyncTab(), tr("同步"));

    QVBoxLayout *layout = new QVBoxLayout(this);
    layout->setContentsMargins(ui::Spacing::M, ui::Spacing::M,
                               ui::Spacing::M, ui::Spacing::M);
    layout->setSpacing(ui::Spacing::XS);
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

void MemoryPanel::showSyncTab()
{
    if (m_tabs) {
        m_tabs->setCurrentIndex(2);
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
    m_conflictEmptyLabel->setText(tr("暂无冲突记录"));
    m_conflictEmptyLabel->setVisible(!hasConflicts);
    m_conflictList->setVisible(hasConflicts);
    m_conflictErrorLabel->setVisible(false);
    m_conflictRetryButton->setVisible(false);
}

void MemoryPanel::setConflictsLoading()
{
    m_conflictEmptyLabel->setText(tr("正在加载…"));
    m_conflictEmptyLabel->setVisible(true);
    m_conflictList->setVisible(false);
    m_conflictErrorLabel->setVisible(false);
    m_conflictRetryButton->setVisible(false);
}

void MemoryPanel::setConflictsError(const QString &message)
{
    m_conflictErrorLabel->setText(message);
    m_conflictErrorLabel->setVisible(true);
    m_conflictRetryButton->setVisible(true);
    m_conflictEmptyLabel->setVisible(false);
    m_conflictList->setVisible(false);
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
    m_prefEmptyLabel->setText(tr("暂无历史记录"));
    m_prefEmptyLabel->setVisible(!hasHistory);
    m_prefHistoryList->setVisible(hasHistory);
    m_prefErrorLabel->setVisible(false);
    m_prefRetryButton->setVisible(false);
}

void MemoryPanel::setPreferenceHistoryLoading()
{
    m_prefEmptyLabel->setText(tr("正在加载…"));
    m_prefEmptyLabel->setVisible(true);
    m_prefHistoryList->setVisible(false);
    m_prefErrorLabel->setVisible(false);
    m_prefRetryButton->setVisible(false);
}

void MemoryPanel::setPreferenceHistoryError(const QString &message)
{
    m_prefErrorLabel->setText(message);
    m_prefErrorLabel->setVisible(true);
    m_prefRetryButton->setVisible(true);
    m_prefEmptyLabel->setVisible(false);
    m_prefHistoryList->setVisible(false);
}

void MemoryPanel::setPreferenceExtractResult(int count)
{
    m_prefExtractLabel->setStyleSheet(ui::textStyle(ui::Role::Success));
    m_prefExtractLabel->setText(tr("已提取 %1 条偏好").arg(count));
    m_prefExtractLabel->setVisible(true);
}

void MemoryPanel::setPreferenceExtractError(const QString &message)
{
    m_prefExtractLabel->setStyleSheet(ui::textStyle(ui::Role::Error));
    m_prefExtractLabel->setText(message);
    m_prefExtractLabel->setVisible(true);
}

void MemoryPanel::setPreferenceList(const QJsonArray &preferences)
{
    if (!m_prefListCombo) {
        return;
    }
    m_prefListCombo->blockSignals(true);
    m_prefListCombo->clear();
    m_prefListCombo->addItem(tr("从列表选择偏好…"), QString());
    for (const QJsonValue &value : preferences) {
        const QJsonObject pref = value.toObject();
        const QString id = pref.value(QStringLiteral("id")).toString();
        const QString key = pref.value(QStringLiteral("key")).toString();
        const int version = pref.value(QStringLiteral("version")).toInt(1);
        m_prefListCombo->addItem(
            tr("%1 · v%2").arg(key.isEmpty() ? id : key).arg(version), id);
    }
    m_prefListCombo->blockSignals(false);
}

void MemoryPanel::showPairingToken(const QJsonObject &response)
{
    if (m_pairDialog) {
        m_pairDialog->setPairingToken(response);
    }
}

void MemoryPanel::showPairingTokenError(const QString &message)
{
    if (m_pairDialog) {
        m_pairDialog->setPairingTokenError(message);
    }
}

void MemoryPanel::setSyncStatus(const QString &status, bool ok)
{
    if (!m_syncStatusLabel) {
        return;
    }
    m_syncStatusLabel->setText(status);
    m_syncStatusLabel->setStyleSheet(
        ui::textStyle(ok ? ui::Role::Success : ui::Role::Error));
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
        layout->setContentsMargins(ui::Spacing::S, ui::Spacing::XS,
                                   ui::Spacing::S, ui::Spacing::XS);
        layout->setSpacing(ui::Spacing::XS);

        QHBoxLayout *nameRow = new QHBoxLayout();
        const QString displayName =
            name.isEmpty() ? tr("（未命名设备）") : name;
        QLabel *nameLabel = new QLabel(container);
        nameLabel->setObjectName(QStringLiteral("peerNameLabel"));
        nameLabel->setFont(ui::Font::body());
        // 长设备名行内省略，避免把在线状态挤出可视区（布局鲁棒性）。
        nameLabel->setText(elidePeerName(nameLabel->font(), displayName, 220));

        QLabel *stateLabel = new QLabel(peerStateText(isSelf, state), container);
        stateLabel->setObjectName(QStringLiteral("peerStateLabel"));
        if (isSelf || state == QStringLiteral("ONLINE")) {
            stateLabel->setStyleSheet(ui::textStyle(ui::Role::Success));
        } else if (state == QStringLiteral("OFFLINE")) {
            stateLabel->setStyleSheet(ui::textStyle(ui::Role::Muted));
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
            metaLabel->setObjectName(QStringLiteral("peerMetaLabel"));
            metaLabel->setStyleSheet(ui::textStyle(ui::Role::Muted));
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
    layout->setContentsMargins(ui::Spacing::S, ui::Spacing::S,
                               ui::Spacing::S, ui::Spacing::S);

    m_prefHeaderLabel = new QLabel(tr("偏好历史"), page);
    m_prefHeaderLabel->setObjectName(QStringLiteral("prefHeaderLabel"));
    m_prefHeaderLabel->setFont(ui::Font::title());

    m_prefIdInput = new QLineEdit(page);
    m_prefIdInput->setAccessibleName(tr("偏好 ID 输入框"));
    m_prefIdInput->setPlaceholderText(tr("偏好 ID（如 pref_…）"));
    QPushButton *loadButton = new QPushButton(tr("加载历史"), page);
    loadButton->setCursor(Qt::PointingHandCursor);
    connect(loadButton, &QPushButton::clicked, this, [this]() {
        emit historyRequested(m_prefIdInput->text().trimmed());
    });
    connect(m_prefIdInput, &QLineEdit::returnPressed, this, [this]() {
        emit historyRequested(m_prefIdInput->text().trimmed());
    });

    QHBoxLayout *inputRow = new QHBoxLayout();
    inputRow->addWidget(m_prefIdInput, 1);
    inputRow->addWidget(loadButton);

    // 偏好列表选择器（GET /preferences）：免手动输入 ID。
    m_prefListCombo = new QComboBox(page);
    m_prefListCombo->setObjectName(QStringLiteral("prefListCombo"));
    m_prefListCombo->setAccessibleName(tr("已提取偏好选择"));
    m_prefListCombo->addItem(tr("从列表选择偏好…"), QString());
    connect(m_prefListCombo, QOverload<int>::of(&QComboBox::currentIndexChanged),
            this, [this](int index) {
                const QString id = m_prefListCombo->itemData(index).toString();
                if (!id.isEmpty()) {
                    emit historyRequested(id);
                    m_prefListCombo->setCurrentIndex(0);
                }
            });

    QPushButton *refreshPrefButton = new QPushButton(tr("刷新列表"), page);
    refreshPrefButton->setObjectName(QStringLiteral("prefRefreshButton"));
    refreshPrefButton->setAccessibleName(tr("刷新偏好列表"));
    refreshPrefButton->setCursor(Qt::PointingHandCursor);
    connect(refreshPrefButton, &QPushButton::clicked, this,
            &MemoryPanel::preferencesRefreshRequested);

    QHBoxLayout *comboRow = new QHBoxLayout();
    comboRow->addWidget(m_prefListCombo, 1);
    comboRow->addWidget(refreshPrefButton);

    m_prefExtractButton = new QPushButton(tr("提取偏好"), page);
    m_prefExtractButton->setObjectName(QStringLiteral("prefExtractButton"));
    m_prefExtractButton->setAccessibleName(tr("从最近录入提取偏好"));
    m_prefExtractButton->setCursor(Qt::PointingHandCursor);
    connect(m_prefExtractButton, &QPushButton::clicked, this,
            &MemoryPanel::extractPreferencesRequested);

    m_prefExtractLabel = new QLabel(page);
    m_prefExtractLabel->setObjectName(QStringLiteral("prefExtractLabel"));
    m_prefExtractLabel->setWordWrap(true);
    m_prefExtractLabel->setVisible(false);

    QHBoxLayout *extractRow = new QHBoxLayout();
    extractRow->addWidget(m_prefExtractButton);
    extractRow->addWidget(m_prefExtractLabel, 1);

    m_prefErrorLabel = new QLabel(page);
    m_prefErrorLabel->setObjectName(QStringLiteral("prefErrorLabel"));
    m_prefErrorLabel->setStyleSheet(ui::textStyle(ui::Role::Error));
    m_prefErrorLabel->setWordWrap(true);
    m_prefErrorLabel->setVisible(false);
    m_prefRetryButton = new QPushButton(tr("重试"), page);
    m_prefRetryButton->setObjectName(QStringLiteral("prefRetryButton"));
    m_prefRetryButton->setAccessibleName(tr("重试加载偏好历史"));
    m_prefRetryButton->setFlat(true);
    m_prefRetryButton->setVisible(false);
    m_prefRetryButton->setCursor(Qt::PointingHandCursor);
    connect(m_prefRetryButton, &QPushButton::clicked, this,
            &MemoryPanel::preferenceRetryRequested);

    QHBoxLayout *prefErrorRow = new QHBoxLayout();
    prefErrorRow->addWidget(m_prefErrorLabel, 1);
    prefErrorRow->addWidget(m_prefRetryButton);

    m_prefEmptyLabel = new QLabel(tr("暂无历史记录"), page);
    m_prefEmptyLabel->setObjectName(QStringLiteral("prefEmptyLabel"));
    m_prefEmptyLabel->setAlignment(Qt::AlignCenter);
    m_prefHistoryList = new QListWidget(page);
    m_prefHistoryList->setObjectName(QStringLiteral("prefHistoryList"));
    m_prefHistoryList->setVisible(false);

    layout->addWidget(m_prefHeaderLabel);
    layout->addLayout(inputRow);
    layout->addLayout(comboRow);
    layout->addLayout(extractRow);
    layout->addLayout(prefErrorRow);
    layout->addWidget(m_prefEmptyLabel);
    layout->addWidget(m_prefHistoryList, 1);
    return page;
}

QWidget *MemoryPanel::createConflictTab()
{
    QWidget *page = new QWidget();
    QVBoxLayout *layout = new QVBoxLayout(page);
    layout->setContentsMargins(ui::Spacing::S, ui::Spacing::S,
                               ui::Spacing::S, ui::Spacing::S);

    QLabel *titleLabel = new QLabel(tr("冲突"), page);
    titleLabel->setObjectName(QStringLiteral("panelTitleLabel"));
    titleLabel->setFont(ui::Font::title());

    m_conflictEmptyLabel = new QLabel(tr("暂无冲突记录"), page);
    m_conflictEmptyLabel->setObjectName(QStringLiteral("conflictEmptyLabel"));
    m_conflictEmptyLabel->setAlignment(Qt::AlignCenter);
    m_conflictList = new QListWidget(page);
    m_conflictList->setObjectName(QStringLiteral("conflictList"));
    m_conflictList->setWordWrap(true);
    m_conflictList->setVisible(false);

    m_conflictErrorLabel = new QLabel(page);
    m_conflictErrorLabel->setObjectName(QStringLiteral("conflictErrorLabel"));
    m_conflictErrorLabel->setStyleSheet(ui::textStyle(ui::Role::Error));
    m_conflictErrorLabel->setWordWrap(true);
    m_conflictErrorLabel->setVisible(false);
    m_conflictRetryButton = new QPushButton(tr("重试"), page);
    m_conflictRetryButton->setObjectName(QStringLiteral("conflictRetryButton"));
    m_conflictRetryButton->setAccessibleName(tr("重试加载冲突列表"));
    m_conflictRetryButton->setFlat(true);
    m_conflictRetryButton->setVisible(false);
    m_conflictRetryButton->setCursor(Qt::PointingHandCursor);
    connect(m_conflictRetryButton, &QPushButton::clicked, this,
            &MemoryPanel::conflictRetryRequested);

    QHBoxLayout *conflictErrorRow = new QHBoxLayout();
    conflictErrorRow->addWidget(m_conflictErrorLabel, 1);
    conflictErrorRow->addWidget(m_conflictRetryButton);

    layout->addWidget(titleLabel);
    layout->addLayout(conflictErrorRow);
    layout->addWidget(m_conflictEmptyLabel);
    layout->addWidget(m_conflictList, 1);
    return page;
}

QWidget *MemoryPanel::createSyncTab()
{
    QWidget *page = new QWidget();
    QVBoxLayout *layout = new QVBoxLayout(page);
    layout->setContentsMargins(ui::Spacing::S, ui::Spacing::S,
                               ui::Spacing::S, ui::Spacing::S);

    QLabel *titleLabel = new QLabel(tr("同步"), page);
    titleLabel->setObjectName(QStringLiteral("panelTitleLabel"));
    titleLabel->setFont(ui::Font::title());

    m_syncStatusLabel = new QLabel(
        tr("正在加载同步状态…"), page);
    m_syncStatusLabel->setObjectName(QStringLiteral("syncStatusLabel"));
    m_syncStatusLabel->setWordWrap(true);
    m_syncStatusLabel->setStyleSheet(ui::textStyle(ui::Role::Muted));

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
    pairButton->setCursor(Qt::PointingHandCursor);
    connect(pairButton, &QPushButton::clicked, this, [this]() {
        if (!m_pairDialog) {
            m_pairDialog = new PairDialog(this);
            connect(m_pairDialog, &PairDialog::pairRequested,
                    this, &MemoryPanel::pairRequested);
            connect(m_pairDialog, &PairDialog::tokenGenerationRequested,
                    this, &MemoryPanel::pairingTokenRequested);
        }
        m_pairDialog->showAndFocus();
    });

    QPushButton *refreshButton = new QPushButton(tr("刷新"), page);
    refreshButton->setObjectName(QStringLiteral("syncRefreshButton"));
    refreshButton->setAccessibleName(tr("刷新节点与同步状态"));
    refreshButton->setCursor(Qt::PointingHandCursor);
    connect(refreshButton, &QPushButton::clicked, this, [this]() {
        m_syncStatusLabel->setText(tr("正在加载同步状态…"));
        m_syncStatusLabel->setStyleSheet(ui::textStyle(ui::Role::Muted));
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
