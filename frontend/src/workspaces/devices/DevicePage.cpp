#include "DevicePage.h"
#include "PairingDialog.h"
#include "services/HttpBackendTransport.h"
#include <QCheckBox>
#include <QHBoxLayout>
#include <QJsonArray>
#include <QLabel>
#include <QListWidget>
#include <QMessageBox>
#include <QPushButton>
#include <QShowEvent>
#include <QTimer>
#include <QVBoxLayout>

namespace pixiu {
DevicePage::DevicePage(QWidget *parent, BackendTransport *transport)
    : QWidget(parent), m_transport(transport ? transport : new HttpBackendTransport(this))
{
    m_refreshTimer = new QTimer(this);
    m_refreshTimer->setSingleShot(true);
    m_refreshTimer->setInterval(500);
    connect(m_refreshTimer, &QTimer::timeout, this, [this]() {
        if (m_refreshNeeded && isVisible() && m_pending == Pending::None && !hasUnsavedChanges()) refresh();
    });
    auto *outer = new QHBoxLayout(this);
    outer->setContentsMargins(28, 24, 28, 24);
    auto *content = new QWidget(this);
    content->setMaximumWidth(1040);
    outer->addWidget(content, 1);
    outer->addStretch();
    auto *layout = new QVBoxLayout(content);
    layout->setContentsMargins(0, 0, 0, 0);
    layout->setSpacing(12);
    auto *title = new QLabel(tr("设备共享"), this);
    title->setStyleSheet("font-size: 22px; font-weight: 600;");
    layout->addWidget(title);
    auto *notice = new QLabel(tr("个人记忆不参与共享域同步。设备发现只表示收到广播，本地信任与节点记录状态不证明对端在线或数据已经送达。"), this);
    notice->setWordWrap(true);
    layout->addWidget(notice);
    m_summary = new QLabel(tr("同步状态尚未读取。"), this);
    m_summary->setObjectName(QStringLiteral("deviceSummary"));
    m_summary->setWordWrap(true);
    m_summary->setTextFormat(Qt::PlainText);
    layout->addWidget(m_summary);
    m_enabled = new QCheckBox(tr("启用同步网络"), this);
    m_enabled->setObjectName(QStringLiteral("deviceEnabled"));
    m_paused = new QCheckBox(tr("暂停传输（保留发现与配对能力）"), this);
    m_paused->setObjectName(QStringLiteral("devicePaused"));
    layout->addWidget(m_enabled);
    layout->addWidget(m_paused);
    auto *buttons = new QHBoxLayout;
    m_refresh = new QPushButton(tr("重试连接"), this);
    m_refresh->setObjectName(QStringLiteral("deviceRefresh"));
    m_save = new QPushButton(tr("保存同步设置"), this);
    m_save->setObjectName(QStringLiteral("deviceSave"));
    buttons->addWidget(m_refresh);
    buttons->addWidget(m_save);
    buttons->addStretch();
    layout->addLayout(buttons);
    layout->addWidget(new QLabel(tr("本机与本地信任节点"), this));
    m_peers = new QListWidget(this);
    m_peers->setObjectName(QStringLiteral("devicePeers"));
    m_peers->setAccessibleName(tr("本机与本地信任节点"));
    m_peers->setWordWrap(true);
    layout->addWidget(m_peers, 1);
    m_revoke = new QPushButton(tr("移除所选设备…"), this);
    m_revoke->setObjectName(QStringLiteral("deviceRevoke"));

    m_leave = new QPushButton(tr("断开所有设备…"), this);
    m_leave->setObjectName(QStringLiteral("deviceLeave"));

    auto *pair = new QPushButton(tr("添加设备…"), this);
    pair->setObjectName(QStringLiteral("devicePair"));

    auto *pairing = new PairingDialog(this);
    pairing->setWindowModality(Qt::WindowModal);
    connect(pair, &QPushButton::clicked, this, [pairing]() {
        pairing->show();
        pairing->raise();
        pairing->activateWindow();
    });
    connect(pairing, &PairingDialog::localTrustEstablished, this, [this]() {
        m_status->setText(tr("配对页已建立本地信任，请刷新节点；对端信任及实际传输仍须核对。"));
    });
    m_discover = new QPushButton(tr("查找附近设备"), this);
    m_discover->setObjectName(QStringLiteral("deviceDiscover"));
    auto *deviceActions = new QHBoxLayout;
    deviceActions->addWidget(pair);
    deviceActions->addWidget(m_discover);
    deviceActions->addStretch();
    deviceActions->addWidget(m_revoke);
    layout->addLayout(deviceActions);
    auto *leaveRow = new QHBoxLayout;
    leaveRow->addWidget(m_leave);
    leaveRow->addStretch();
    layout->addLayout(leaveRow);
    m_discovered = new QListWidget(this);
    m_discovered->setObjectName(QStringLiteral("deviceDiscovered"));
    m_discovered->setAccessibleName(tr("附近设备广播记录"));
    m_discovered->setWordWrap(true);
    layout->addWidget(m_discovered, 1);
    m_status = new QLabel(tr("读取会覆盖未保存的开关编辑；关闭网络不会删除记忆或解除已有信任。"), this);
    m_status->setObjectName(QStringLiteral("deviceStatus"));
    m_status->setTextFormat(Qt::PlainText);
    m_status->setWordWrap(true);
    layout->addWidget(m_status);
    connect(m_refresh, &QPushButton::clicked, this, &DevicePage::refresh);
    connect(m_leave, &QPushButton::clicked, this, [this]() {
        if (m_pending != Pending::None) return;
        m_pending = Pending::LeavePeers;
        m_leaveQueue.clear();
        controls();
        m_status->setText(tr("正在读取将解除的信任节点，尚未执行更改…"));
        m_transport->listPeers();
    });
    connect(m_peers, &QListWidget::currentRowChanged, this, [this]() { controls(); });
    for (auto *check : {m_enabled, m_paused})
        connect(check, &QCheckBox::toggled, this, [this]() {
            if (m_pending == Pending::None && m_loaded)
                m_status->setText(tr("同步开关有未保存的修改。"));
            scheduleRefresh();
        });
    connect(m_save, &QPushButton::clicked, this, [this]() {
        if (!m_loaded || m_pending != Pending::None) return;
        m_pending = Pending::Settings;
        controls();
        m_status->setText(tr("正在保存同步设置…"));
        m_transport->updateSyncSettings(m_enabled->isChecked(), m_paused->isChecked());
    });
    connect(m_discover, &QPushButton::clicked, this, [this]() {
        if (m_pending != Pending::None) return;
        m_discovered->clear();
        m_pending = Pending::Discover;
        controls();
        m_status->setText(tr("正在读取设备广播记录…"));
        m_transport->discoverDevices();
    });
    connect(m_revoke, &QPushButton::clicked, this, [this]() {
        if (m_pending != Pending::None || !m_peers->currentItem()) return;
        const QString id = m_peers->currentItem()->data(Qt::UserRole).toString();
        if (id.isEmpty()) return;
        QMessageBox confirmation(QMessageBox::Warning, tr("解除本地信任"),
            tr("设备：%1\n解除后本机不再信任此设备。此操作不会删除已有记忆，也不代表对端已移除本机。是否继续？").arg(id),
            QMessageBox::Yes | QMessageBox::No, this);
        confirmation.setDefaultButton(QMessageBox::No);
        m_pending = Pending::ReviewRevoke;
        controls();
        if (confirmation.exec() != QMessageBox::Yes) { finish(tr("已取消，未解除信任。")); return; }
        m_revoking = id;
        m_pending = Pending::Revoke;
        controls();
        m_status->setText(tr("正在解除本地信任…"));
        m_transport->revokePeer(id);
    });
    connect(m_transport, &BackendTransport::syncStatusResult, this, [this](const QJsonObject &state) {
        if (m_pending != Pending::Status) return;
        if (!state.value("enabled").isBool() || !state.value("paused").isBool()
            || !state.value("domain").isString() || !state.value("peers_total").isDouble()
            || !state.value("pending_outgoing_ops").isDouble() || !state.value("total_ops_synced").isDouble()) {
            finish(tr("同步状态响应不完整，禁止修改开关，请重新读取。"));
            return;
        }
        m_loaded = true;
        m_haveSnapshot = true;
        m_savedEnabled = state.value("enabled").toBool();
        m_savedPaused = state.value("paused").toBool();
        m_enabled->setChecked(state.value("enabled").toBool());
        m_paused->setChecked(state.value("paused").toBool());
        m_summary->setText(tr("共享域：%1\n节点记录：%2（含本机） · 待发操作：%3 · 累计同步计数：%4\n这是后端记录，不是实时网络连通性检测。")
            .arg(state.value("domain").toString()).arg(state.value("peers_total").toInt())
            .arg(state.value("pending_outgoing_ops").toInt()).arg(state.value("total_ops_synced").toInt()));
        m_pending = Pending::Peers;
        m_status->setText(tr("状态已读取，正在读取节点…"));
        m_transport->listPeers();
    });
    connect(m_transport, &BackendTransport::peersResult, this, [this](const QJsonObject &response) {
        if (m_pending != Pending::Peers && m_pending != Pending::LeavePeers && m_pending != Pending::LeaveVerify) return;
        if (!response.value("peers").isArray()) { finish(tr("节点响应不完整，请刷新重试。")); return; }
        const auto peers = response.value("peers").toArray();
        for (const auto &value : peers) {
            const auto peer = value.toObject();
            if (peer.value("id").toString().isEmpty() || !peer.value("is_self").isBool()) {
                finish(tr("节点响应包含无效记录，请刷新重试。")); return;
            }
        }
        if (m_pending == Pending::LeavePeers || m_pending == Pending::LeaveVerify) {
            QStringList ids;
            for (const auto &value : peers) {
                const auto peer = value.toObject();
                const auto id = peer.value("id").toString();
                if (!peer.value("is_self").toBool() && !ids.contains(id)) ids << id;
            }
            if (m_pending == Pending::LeaveVerify) {
                m_peers->clear();
                m_discovered->clear();
                finish(ids.isEmpty() ? tr("已核对：本机无剩余信任节点，网络设置已关闭。已有记忆保留，对端状态未验证。")
                    : tr("退出未完成：网络设置已关闭，但仍有信任节点（可能有并发配对）。请刷新核对。"));
                return;
            }
            QMessageBox confirmation(QMessageBox::Warning, tr("退出本地同步网络"),
                tr("将逐个解除以下 %1 个设备的本地信任，然后关闭网络。已有记忆不会删除；对端不会自动移除本机。操作不是原子事务，中途失败可能仅完成部分解除。\n\n%2\n\n是否继续？")
                    .arg(ids.size()).arg(ids.isEmpty() ? tr("没有需要解除的节点，仅关闭网络。") : ids.join(QLatin1Char('\n'))),
                QMessageBox::Yes | QMessageBox::No, this);
            confirmation.setDefaultButton(QMessageBox::No);
            if (confirmation.exec() != QMessageBox::Yes) { finish(tr("已取消，未提交退出操作。")); return; }
            m_leaveQueue = ids;
            m_loaded = false;
            leaveNext();
            return;
        }
        m_peers->clear();
        for (const auto &value : peers) {
            const auto peer = value.toObject();
            const bool self = peer.value("is_self").toBool();
            auto *item = new QListWidgetItem(tr("%1%2\n%3 · 记录状态：%4")
                .arg(peer.value("name").toString(), self ? tr("（本机）") : QString(),
                     peer.value("id").toString(), peer.value("status").toString()), m_peers);
            if (!self) item->setData(Qt::UserRole, peer.value("id").toString());
            if (!self && peer.value("id").toString() == m_restorePeer) m_peers->setCurrentItem(item);
        }
        m_restorePeer.clear();
        finish(peers.isEmpty() ? tr("后端没有返回节点记录。") : tr("节点记录已刷新。"));
    });
    connect(m_transport, &BackendTransport::devicesLoaded, this, [this](const QJsonObject &response) {
        if (m_pending != Pending::Discover) return;
        if (!response.value("devices").isArray()) { finish(tr("设备发现响应不完整，请重试。")); return; }
        const auto devices = response.value("devices").toArray();
        for (const auto &value : devices) {
            const auto device = value.toObject();
            if (device.value("device_id").toString().isEmpty() || !device.value("paired").isBool()) {
                m_discovered->clear();
                finish(tr("设备发现包含无效记录，请重试。")); return;
            }
            m_discovered->addItem(tr("%1\n%2 · %3").arg(device.value("device_name").toString(),
                device.value("device_id").toString(), device.value("paired").toBool() ? tr("已有本地信任记录") : tr("尚无本地信任记录")));
        }
        finish(devices.isEmpty() ? tr("未读取到设备广播；不能据此判断附近没有设备，发现服务也可能未运行。") : tr("已读取设备广播，不代表已完成配对或同步。"));
    });
    connect(m_transport, &BackendTransport::settingsResult, this, [this](const QJsonObject &response) {
        if (m_pending != Pending::Settings && m_pending != Pending::LeaveSettings) return;
        if (!response.value("enabled").isBool() || !response.value("paused").isBool()) {
            m_loaded = false;
            finish(tr("设置响应不完整，是否生效尚未确认，请刷新状态。")); return;
        }
        m_enabled->setChecked(response.value("enabled").toBool());
        m_paused->setChecked(response.value("paused").toBool());
        m_haveSnapshot = true;
        m_savedEnabled = response.value("enabled").toBool();
        m_savedPaused = response.value("paused").toBool();
        if (m_pending == Pending::LeaveSettings) {
            if (response.value("enabled").toBool()) {
                finish(tr("退出未完成：后端未确认网络设置关闭，信任解除可能已部分生效。请刷新核对。"));
                return;
            }
            m_pending = Pending::LeaveVerify;
            m_status->setText(tr("网络设置已关闭，正在核对剩余信任节点…"));
            m_transport->listPeers();
            return;
        }
        finish(tr("后端已保存同步设置；网络证书与环境仍会影响实际传输。"));
    });
    connect(m_transport, &BackendTransport::revokeResult, this, [this](const QJsonObject &response) {
        if (m_pending != Pending::Revoke && m_pending != Pending::LeaveRevoke) return;
        if (response.value("status").toString() != "revoked" || response.value("peer_id").toString() != m_revoking) {
            finish(tr("解除信任响应不匹配，未确认成功，请刷新核对。")); return;
        }
        if (m_pending == Pending::LeaveRevoke) {
            m_leaveQueue.removeFirst();
            leaveNext();
            return;
        }
        m_peers->clear();
        finish(tr("已解除所选设备的本地信任。请刷新节点与设备广播；对端状态未验证。"));
    });
    connect(m_transport, &BackendTransport::errorOccurred, this, [this](const QString &, const QString &message, const QString &) {
        if (m_pending == Pending::None) return;
        if (m_pending == Pending::LeaveRevoke || m_pending == Pending::LeaveSettings || m_pending == Pending::LeaveVerify) {
            m_loaded = false;
            m_peers->clear();
            finish(tr("退出未完成：%1。可能已有部分信任被解除；停止后续操作，请刷新核对，不会自动重试。").arg(message));
            return;
        }
        if (m_pending == Pending::Settings) m_loaded = false;
        finish(tr("操作失败：%1。写操作是否生效未确认，请刷新核对后再操作。").arg(message));
    });
    controls();
}
void DevicePage::leaveNext()
{
    if (m_leaveQueue.isEmpty()) {
        m_pending = Pending::LeaveSettings;
        controls();
        m_status->setText(tr("所选节点的解除响应已确认，正在关闭网络…"));
        m_transport->updateSyncSettings(false, false);
    } else {
        m_revoking = m_leaveQueue.first();
        m_pending = Pending::LeaveRevoke;
        controls();
        m_status->setText(tr("正在解除设备 %1；队列剩余 %2 个。已完成操作不会自动撤销。")
            .arg(m_revoking).arg(m_leaveQueue.size()));
        m_transport->revokePeer(m_revoking);
    }
}
void DevicePage::refresh()
{
    if (m_pending != Pending::None) return;
    m_refreshNeeded = false;
    m_refreshTimer->stop();
    m_restorePeer = m_peers->currentItem() ? m_peers->currentItem()->data(Qt::UserRole).toString() : QString();
    m_loaded = false;
    m_pending = Pending::Status;
    m_peers->clear();
    m_summary->setText(tr("正在读取同步状态…"));
    m_status->setText(tr("正在读取同步状态…"));
    controls();
    m_transport->syncStatus();
}
bool DevicePage::hasUnsavedChanges() const
{
    return m_haveSnapshot && (m_enabled->isChecked() != m_savedEnabled
        || m_paused->isChecked() != m_savedPaused);
}
void DevicePage::notifyDataChanged()
{
    m_refreshNeeded = true;
    scheduleRefresh();
}
void DevicePage::scheduleRefresh()
{
    if (m_refreshNeeded && isVisible() && m_pending == Pending::None
        && !hasUnsavedChanges() && !m_refreshTimer->isActive()) m_refreshTimer->start();
}
void DevicePage::showEvent(QShowEvent *event)
{
    QWidget::showEvent(event);
    scheduleRefresh();
}
void DevicePage::finish(const QString &message)
{
    m_pending = Pending::None;
    m_status->setText(message);
    controls();
}
void DevicePage::controls()
{
    const bool idle = m_pending == Pending::None;
    m_refresh->setEnabled(idle);
    m_refresh->setVisible(!m_loaded && idle);
    m_discover->setEnabled(idle);
    m_leave->setEnabled(idle);
    if (auto *pair = findChild<QPushButton *>(QStringLiteral("devicePair"))) pair->setEnabled(idle);
    m_save->setEnabled(idle && m_loaded);
    m_enabled->setEnabled(idle && m_loaded);
    m_paused->setEnabled(idle && m_loaded);
    m_peers->setEnabled(idle);
    m_revoke->setEnabled(idle && m_peers->currentItem()
        && !m_peers->currentItem()->data(Qt::UserRole).toString().isEmpty());
    scheduleRefresh();
}
}
