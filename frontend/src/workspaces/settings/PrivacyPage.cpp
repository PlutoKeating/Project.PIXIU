#include "PrivacyPage.h"
#include "services/HttpBackendTransport.h"
#include <QAction>
#include <QApplication>
#include <QCheckBox>
#include <QClipboard>
#include <QDateTime>
#include <QDir>
#include <QHBoxLayout>
#include <QJsonArray>
#include <QLabel>
#include <QListWidget>
#include <QPlainTextEdit>
#include <QPushButton>
#include <QShowEvent>
#include <QTimer>
#include <QVBoxLayout>
#include <cmath>
#include <utility>

namespace pixiu {
PrivacyPage::PrivacyPage(QWidget *parent, BackendTransport *transport)
    : QWidget(parent), m_transport(transport ? transport : new HttpBackendTransport(this))
{
    auto *inputStatus = new QLabel(tr("正在检查图片和扫描 PDF 读取状态…"), this);
    inputStatus->setObjectName("mediaInputStatus"); inputStatus->setWordWrap(true);
    auto *mediaHttp = new HttpBackendTransport(this);
    connect(mediaHttp, &HttpBackendTransport::inputCapabilitiesResult, this, [inputStatus](const QJsonObject &result) {
        inputStatus->setText(result.value("message").toString());
    });
    auto *mediaTimer = new QTimer(this); mediaTimer->setInterval(15000);
    connect(mediaTimer, &QTimer::timeout, this, [this, mediaHttp] { if (isVisible()) mediaHttp->inputCapabilities(); });
    mediaTimer->start(); mediaHttp->inputCapabilities();
    m_refreshTimer = new QTimer(this);
    m_refreshTimer->setSingleShot(true);
    m_refreshTimer->setInterval(500);
    connect(m_refreshTimer, &QTimer::timeout, this, [this]() {
        if (m_refreshNeeded && isVisible() && m_pending == Pending::None && m_offset == 0) loadLogs(0);
    });
    auto *layout = new QVBoxLayout(this);
    layout->addWidget(inputStatus);
    m_enabled = new QCheckBox(tr("启用自动采集（关闭后暂停采集，不删除已有记忆）"), this);
    m_enabled->setObjectName(QStringLiteral("privacyEnabled"));
    m_directory = new QCheckBox(tr("目录文件变化"), this);
    m_directory->setObjectName(QStringLiteral("privacyDirectory"));
    m_behavior = new QCheckBox(tr("应用行为统计（桌面环境不同，采集质量可能降级）"), this);
    m_behavior->setObjectName(QStringLiteral("privacyBehavior"));
    layout->addWidget(m_enabled);
    layout->addWidget(m_directory);
    layout->addWidget(m_behavior);
    auto *unavailable = new QLabel(tr("剪贴板与自动截图：当前版本未实现采集。保存时保留已有配置字段，不将其宣称为可用能力。"), this);
    unavailable->setWordWrap(true);
    layout->addWidget(unavailable);
    layout->addWidget(new QLabel(tr("监视所选目录的直接子文件，不包含子目录。文本支持 TXT、Markdown、CSV（不超过 1 MB）；图片和扫描 PDF 自动使用当前聊天模型；不可用时不读取。每行填写一个授权目录。"), this));
    m_directories = new QPlainTextEdit(this);
    m_directories->setObjectName(QStringLiteral("privacyDirectories"));
    m_directories->setAccessibleName(tr("监视目录列表"));
    layout->addWidget(m_directories, 1);
    m_browse = new QPushButton(tr("添加文件夹…"), this);
    m_browse->setObjectName(QStringLiteral("privacyBrowse"));
    layout->addWidget(m_browse);
    connect(m_browse, &QPushButton::clicked, this, [this]() {
        if (!m_directoryPicker || !m_loaded || m_pending != Pending::None) return;
        m_pending = Pending::Directory;
        controls();
        const QString selected = m_directoryPicker(this);
        m_pending = Pending::None;
        controls();
        if (selected.isEmpty()) {
            m_status->setText(tr("已取消选择，配置草稿未更改。"));
            return;
        }
        // The backend and editor use trimmed, newline-separated paths. Refuse
        // an unrepresentable path rather than silently authorizing another one.
        if (!QDir::isAbsolutePath(selected) || selected != selected.trimmed()
            || selected.contains(QLatin1Char('\n')) || selected.contains(QLatin1Char('\r'))) {
            m_status->setText(tr("未添加：目录须为绝对路径，且不能含前后空白或换行。"));
            return;
        }
        QString draft = m_directories->toPlainText();
        for (const auto &line : draft.split(QLatin1Char('\n'))) {
            if (line.trimmed() == selected) {
                m_status->setText(tr("目录已在草稿中，未重复添加；尚未保存配置。"));
                return;
            }
        }
        if (!draft.isEmpty() && !draft.endsWith(QLatin1Char('\n'))) draft += QLatin1Char('\n');
        m_directories->setPlainText(draft + selected);
        m_status->setText(tr("目录已加入草稿；请核对范围后保存。未自动开启采集。"));
    });
    m_load = new QPushButton(tr("重试读取设置"), this);
    m_load->setObjectName(QStringLiteral("privacyLoad"));
    m_save = new QPushButton(tr("保存设置"), this);
    m_save->setObjectName(QStringLiteral("privacySave"));
    auto *buttons = new QHBoxLayout;
    buttons->addWidget(m_load);
    buttons->addWidget(m_save);
    layout->addLayout(buttons);
    m_status = new QLabel(tr("先读取后端配置。读取会替换此页未保存的编辑。"), this);
    m_status->setObjectName(QStringLiteral("privacyStatus"));
    m_status->setWordWrap(true);
    m_status->setTextFormat(Qt::PlainText);
    layout->addWidget(m_status);
    auto edited = [this]() {
        if (m_loaded && m_pending == Pending::None)
            m_status->setText(tr("配置有未保存的修改；点击保存后才提交到后端。重新读取会覆盖这些编辑。"));
    };
    for (auto *check : {m_enabled, m_directory, m_behavior})
        connect(check, &QCheckBox::toggled, this, edited);
    connect(m_directories, &QPlainTextEdit::textChanged, this, edited);
    m_events = new QListWidget(this);
    m_events->setObjectName(QStringLiteral("privacyEvents"));
    m_events->setAccessibleName(tr("采集日志，包含 UTC 时间及关联标识"));
    m_events->setAccessibleDescription(tr("选择记录后可右键或按 Ctrl+C 复制；公开前请核对文件名和标识中的私人信息。"));
    m_events->setWordWrap(true);
    auto *copy = new QAction(tr("复制所选日志（公开前核对私人信息）"), m_events);
    copy->setObjectName(QStringLiteral("copyCaptureLog"));
    copy->setShortcut(QKeySequence::Copy);
    copy->setShortcutContext(Qt::WidgetShortcut);
    copy->setEnabled(false);
    m_events->addAction(copy);
    m_events->setContextMenuPolicy(Qt::ActionsContextMenu);
    connect(m_events, &QListWidget::currentItemChanged, copy, [this, copy]() {
        copy->setEnabled(m_events->currentItem() != nullptr);
    });
    connect(copy, &QAction::triggered, this, [this]() {
        if (auto *item = m_events->currentItem()) QApplication::clipboard()->setText(item->text());
    });
    layout->addWidget(m_events, 1);
    m_logs = new QPushButton(tr("刷新采集日志"), this);
    m_logs->setObjectName(QStringLiteral("privacyLogs"));
    m_previous = new QPushButton(tr("上一页"), this);
    m_next = new QPushButton(tr("下一页"), this);
    auto *paging = new QHBoxLayout;
    paging->addWidget(m_logs);
    paging->addStretch();
    paging->addWidget(m_previous);
    paging->addWidget(m_next);
    layout->addLayout(paging);
    connect(m_load, &QPushButton::clicked, this, [this]() {
        if (m_pending != Pending::None) return;
        m_pending = Pending::Load;
        controls();
        m_status->setText(tr("正在读取配置…"));
        m_transport->monitorConfig();
    });
    connect(m_save, &QPushButton::clicked, this, [this]() {
        if (m_pending != Pending::None || !m_loaded) return;
        QJsonArray directories;
        QStringList seen;
        for (const auto &line : m_directories->toPlainText().split(QLatin1Char('\n'))) {
            const QString path = line.trimmed();
            if (path.isEmpty() || seen.contains(path)) continue;
            if (!QDir::isAbsolutePath(path)) {
                m_status->setText(tr("目录必须是绝对路径，配置尚未提交。"));
                return;
            }
            seen << path;
            directories.append(path);
        }
        QJsonObject payload = m_config;
        auto sources = payload.value(QStringLiteral("sources")).toObject();
        sources.insert(QStringLiteral("directory"), m_directory->isChecked());
        sources.insert(QStringLiteral("behavior"), m_behavior->isChecked());
        payload.insert(QStringLiteral("sources"), sources);
        payload.insert(QStringLiteral("enabled"), m_enabled->isChecked());
        payload.insert(QStringLiteral("directories"), directories);
        m_pending = Pending::Save;
        controls();
        m_status->setText(tr("正在保存配置…"));
        m_transport->updateMonitorConfig(payload);
    });
    connect(m_transport, &BackendTransport::configResult, this, [this](const QJsonObject &config) {
        if (m_pending != Pending::Load && m_pending != Pending::Save) return;
        m_pending = Pending::None;
        const auto sources = config.value(QStringLiteral("sources")).toObject();
        if (!config.value("enabled").isBool() || !config.value("directories").isArray()
            || !sources.value("directory").isBool() || !sources.value("behavior").isBool()
            || !sources.value("clipboard").isBool() || !sources.value("screenshot").isBool()) {
            m_loaded = false;
            m_status->setText(tr("配置响应不完整，禁止保存，请重新读取。"));
            controls();
            return;
        }
        m_config = config;
        m_loaded = true;
        m_enabled->setChecked(config.value("enabled").toBool());
        m_directory->setChecked(sources.value("directory").toBool());
        m_behavior->setChecked(sources.value("behavior").toBool());
        QStringList paths;
        for (const auto &path : config.value("directories").toArray()) paths << path.toString();
        m_directories->setPlainText(paths.join(QLatin1Char('\n')));
        m_status->setText(tr("隐私设置已更新。"));
        controls();
    });
    connect(m_logs, &QPushButton::clicked, this, [this]() { loadLogs(0); });
    connect(m_previous, &QPushButton::clicked, this, [this]() { loadLogs(qMax(0, m_offset - 50)); });
    connect(m_next, &QPushButton::clicked, this, [this]() { loadLogs(m_offset + 50); });
    connect(m_transport, &BackendTransport::monitorLogResult, this, [this](const QJsonArray &events) {
        if (m_pending != Pending::Logs) return;
        m_pending = Pending::None;
        m_offset = m_requestedOffset;
        m_more = events.size() == 50;
        m_events->clear();
        for (const auto &value : events) {
            const auto event = value.toObject();
            const auto stamp = event.value("ts");
            const double seconds = stamp.toDouble(-1);
            QString timestamp = tr("未提供或无效");
            // Contract uses integral Unix seconds, not milliseconds. Do not turn
            // a missing/invalid value into epoch zero or the current time.
            if (stamp.isDouble() && std::isfinite(seconds) && seconds >= -62135596800.0
                && seconds <= 253402300799.0 && std::floor(seconds) == seconds) {
                const auto date = QDateTime::fromSecsSinceEpoch(qint64(seconds), Qt::UTC);
                if (date.isValid()) timestamp = date.toString(Qt::ISODate);
            }
            auto identifier = [this, &event](const char *key) {
                const QString id = event.value(QLatin1String(key)).toString();
                return id.isEmpty() ? tr("未提供") : id;
            };
            m_events->addItem(tr("时间（UTC）：%1\n%2 · %3\n%4\n证据 ID：%5\n知识 ID：%6")
                .arg(timestamp, event.value("source").toString(), event.value("status").toString(),
                    event.value("summary").toString(), identifier("evidence_id"), identifier("knowledge_id")));
        }
        m_status->setText(events.isEmpty() ? tr("本页没有采集日志。") : tr("采集日志第 %1 页").arg(m_offset / 50 + 1));
        if (hasUnsavedChanges()) m_status->setText(m_status->text() + tr(" 配置有未保存的修改，日志刷新不会保存配置。"));
        controls();
    });
    connect(m_transport, &BackendTransport::errorOccurred, this, [this](const QString &, const QString &message, const QString &) {
        if (m_pending == Pending::None) return;
        m_pending = Pending::None;
        m_status->setText(tr("操作失败：%1。编辑内容已保留，请重试；未确认配置已生效。").arg(message));
        controls();
    });
    controls();
}
void PrivacyPage::setDirectoryPicker(std::function<QString(QWidget *)> picker)
{
    m_directoryPicker = std::move(picker);
    controls();
}
void PrivacyPage::controls()
{
    const bool idle = m_pending == Pending::None;
    const bool editable = (idle || m_pending == Pending::Logs) && m_loaded;
    for (auto *check : {m_enabled, m_directory, m_behavior}) check->setEnabled(editable);
    m_directories->setEnabled(editable);
    m_browse->setEnabled(idle && m_loaded && bool(m_directoryPicker));
    m_save->setEnabled(idle && m_loaded);
    m_load->setEnabled(idle);
    m_load->setVisible(!m_loaded && idle);
    m_logs->setEnabled(idle);
    m_previous->setEnabled(idle && m_offset > 0);
    m_next->setEnabled(idle && m_more);
    scheduleRefresh();
}
void PrivacyPage::notifyDataChanged()
{
    m_refreshNeeded = true;
    scheduleRefresh();
}
void PrivacyPage::scheduleRefresh()
{
    if (m_refreshNeeded && isVisible() && m_pending == Pending::None && m_offset == 0
        && !m_refreshTimer->isActive()) m_refreshTimer->start();
}
void PrivacyPage::showEvent(QShowEvent *event)
{
    QWidget::showEvent(event);
    if (!m_loaded && m_pending == Pending::None) m_load->click();
    scheduleRefresh();
}
bool PrivacyPage::hasUnsavedChanges() const
{
    if (m_config.isEmpty()) return false;
    const auto sources = m_config.value("sources").toObject();
    QStringList savedPaths;
    for (const auto &path : m_config.value("directories").toArray())
        savedPaths << path.toString();
    return m_enabled->isChecked() != m_config.value("enabled").toBool()
        || m_directory->isChecked() != sources.value("directory").toBool()
        || m_behavior->isChecked() != sources.value("behavior").toBool()
        || m_directories->toPlainText() != savedPaths.join(QLatin1Char('\n'));
}
void PrivacyPage::loadLogs(int offset)
{
    if (m_pending != Pending::None) return;
    if (offset == 0) m_refreshNeeded = false;
    m_refreshTimer->stop();
    m_requestedOffset = offset;
    m_pending = Pending::Logs;
    m_status->setText(tr("正在读取采集日志…"));
    controls();
    m_transport->monitorLog(50, offset);
}
}
