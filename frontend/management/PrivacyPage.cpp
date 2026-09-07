#include "PrivacyPage.h"
#include "services/HttpBackendTransport.h"
#include <QCheckBox>
#include <QDir>
#include <QHBoxLayout>
#include <QJsonArray>
#include <QLabel>
#include <QListWidget>
#include <QPlainTextEdit>
#include <QPushButton>
#include <QVBoxLayout>

namespace pixiu {
PrivacyPage::PrivacyPage(QWidget *parent, BackendTransport *transport)
    : QWidget(parent), m_transport(transport ? transport : new HttpBackendTransport(this))
{
    auto *layout = new QVBoxLayout(this);
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
    layout->addWidget(new QLabel(tr("监视目录：每行一个绝对路径；请只添加允许采集的目录。"), this));
    m_directories = new QPlainTextEdit(this);
    m_directories->setObjectName(QStringLiteral("privacyDirectories"));
    m_directories->setAccessibleName(tr("监视目录列表"));
    layout->addWidget(m_directories, 1);
    m_load = new QPushButton(tr("读取已保存配置"), this);
    m_load->setObjectName(QStringLiteral("privacyLoad"));
    m_save = new QPushButton(tr("保存采集配置"), this);
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
    m_events->setWordWrap(true);
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
        m_status->setText(tr("已读取后端保存的配置。实际采集情况请查看日志；目录权限及桌面能力可能影响采集。"));
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
            m_events->addItem(tr("%1 · %2\n%3").arg(event.value("source").toString(),
                event.value("status").toString(), event.value("summary").toString()));
        }
        m_status->setText(events.isEmpty() ? tr("本页没有采集日志。") : tr("采集日志第 %1 页").arg(m_offset / 50 + 1));
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
void PrivacyPage::controls()
{
    const bool idle = m_pending == Pending::None;
    for (auto *check : {m_enabled, m_directory, m_behavior}) check->setEnabled(idle && m_loaded);
    m_directories->setEnabled(idle && m_loaded);
    m_save->setEnabled(idle && m_loaded);
    m_load->setEnabled(idle);
    m_logs->setEnabled(idle);
    m_previous->setEnabled(idle && m_offset > 0);
    m_next->setEnabled(idle && m_more);
}
void PrivacyPage::loadLogs(int offset)
{
    if (m_pending != Pending::None) return;
    m_requestedOffset = offset;
    m_pending = Pending::Logs;
    m_status->setText(tr("正在读取采集日志…"));
    controls();
    m_transport->monitorLog(50, offset);
}
}
