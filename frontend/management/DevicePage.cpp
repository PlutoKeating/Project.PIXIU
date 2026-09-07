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
#include <QVBoxLayout>

namespace pixiu {
DevicePage::DevicePage(QWidget *parent, BackendTransport *transport)
    : QWidget(parent), m_transport(transport ? transport : new HttpBackendTransport(this))
{
    auto *layout = new QVBoxLayout(this);
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
    m_refresh = new QPushButton(tr("刷新状态与节点"), this);
    m_refresh->setObjectName(QStringLiteral("deviceRefresh"));
    m_save = new QPushButton(tr("保存同步设置"), this);
    m_save->setObjectName(QStringLiteral("deviceSave"));
    buttons->addWidget(m_refresh);
    buttons->addWidget(m_save);
    layout->addLayout(buttons);
    layout->addWidget(new QLabel(tr("本机与本地信任节点"), this));
    m_peers = new QListWidget(this);
    m_peers->setObjectName(QStringLiteral("devicePeers"));
    m_peers->setAccessibleName(tr("本机与本地信任节点"));
    m_peers->setWordWrap(true);
    layout->addWidget(m_peers, 1);
    m_revoke = new QPushButton(tr("解除所选设备的本地信任…"), this);
    m_revoke->setObjectName(QStringLiteral("deviceRevoke"));
    layout->addWidget(m_revoke);
    auto *pair = new QPushButton(tr("交换配对令牌…"), this);
    pair->setObjectName(QStringLiteral("devicePair"));
    layout->addWidget(pair);
    auto *pairing = new PairingDialog(this);
    connect(pair, &QPushButton::clicked, this, [pairing]() {
        pairing->show();
        pairing->raise();
        pairing->activateWindow();
    });
    connect(pairing, &PairingDialog::localTrustEstablished, this, [this]() {
        m_status->setText(tr("配对页已建立本地信任，请刷新节点；对端信任及实际传输仍须核对。"));
    });
    m_discover = new QPushButton(tr("读取附近设备广播"), this);
    m_discover->setObjectName(QStringLiteral("deviceDiscover"));
    layout->addWidget(m_discover);
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
    connect(m_peers, &QListWidget::currentRowChanged, this, [this]() { controls(); });
    for (auto *check : {m_enabled, m_paused})
        connect(check, &QCheckBox::toggled, this, [this]() {
            if (m_pending == Pending::None && m_loaded)
                m_status->setText(tr("同步开关有未保存的修改。"));
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
        if (confirmation.exec() != QMessageBox::Yes) return;
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
        if (m_pending != Pending::Peers) return;
        if (!response.value("peers").isArray()) { finish(tr("节点响应不完整，请刷新重试。")); return; }
        const auto peers = response.value("peers").toArray();
        for (const auto &value : peers) {
            const auto peer = value.toObject();
            if (peer.value("id").toString().isEmpty() || !peer.value("is_self").isBool()) {
                finish(tr("节点响应包含无效记录，请刷新重试。")); return;
            }
        }
        m_peers->clear();
        for (const auto &value : peers) {
            const auto peer = value.toObject();
            const bool self = peer.value("is_self").toBool();
            auto *item = new QListWidgetItem(tr("%1%2\n%3 · 记录状态：%4")
                .arg(peer.value("name").toString(), self ? tr("（本机）") : QString(),
                     peer.value("id").toString(), peer.value("status").toString()), m_peers);
            if (!self) item->setData(Qt::UserRole, peer.value("id").toString());
        }
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
        if (m_pending != Pending::Settings) return;
        if (!response.value("enabled").isBool() || !response.value("paused").isBool()) {
            m_loaded = false;
            finish(tr("设置响应不完整，是否生效尚未确认，请刷新状态。")); return;
        }
        m_enabled->setChecked(response.value("enabled").toBool());
        m_paused->setChecked(response.value("paused").toBool());
        finish(tr("后端已保存同步设置；网络证书与环境仍会影响实际传输。"));
    });
    connect(m_transport, &BackendTransport::revokeResult, this, [this](const QJsonObject &response) {
        if (m_pending != Pending::Revoke) return;
        if (response.value("status").toString() != "revoked" || response.value("peer_id").toString() != m_revoking) {
            finish(tr("解除信任响应不匹配，未确认成功，请刷新核对。")); return;
        }
        m_peers->clear();
        finish(tr("已解除所选设备的本地信任。请刷新节点与设备广播；对端状态未验证。"));
    });
    connect(m_transport, &BackendTransport::errorOccurred, this, [this](const QString &, const QString &message, const QString &) {
        if (m_pending == Pending::None) return;
        if (m_pending == Pending::Settings) m_loaded = false;
        finish(tr("操作失败：%1。写操作是否生效未确认，请刷新核对后再操作。").arg(message));
    });
    controls();
}
void DevicePage::refresh()
{
    if (m_pending != Pending::None) return;
    m_loaded = false;
    m_pending = Pending::Status;
    m_peers->clear();
    m_summary->setText(tr("正在读取同步状态…"));
    m_status->setText(tr("正在读取同步状态…"));
    controls();
    m_transport->syncStatus();
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
    m_discover->setEnabled(idle);
    m_save->setEnabled(idle && m_loaded);
    m_enabled->setEnabled(idle && m_loaded);
    m_paused->setEnabled(idle && m_loaded);
    m_peers->setEnabled(idle);
    m_revoke->setEnabled(idle && m_peers->currentItem()
        && !m_peers->currentItem()->data(Qt::UserRole).toString().isEmpty());
}
}
