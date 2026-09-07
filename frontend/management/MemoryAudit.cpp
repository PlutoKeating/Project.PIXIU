#include "MemoryAudit.h"
#include "MemoryScopes.h"
#include "services/HttpBackendTransport.h"
#include <QComboBox>
#include <QDateTime>
#include <QHBoxLayout>
#include <QJsonArray>
#include <QLabel>
#include <QListWidget>
#include <QPlainTextEdit>
#include <QPushButton>
#include <QShowEvent>
#include <QTimer>
#include <QVBoxLayout>

namespace {
QString resolutionText(const QString &value)
{
    if (value == QStringLiteral("NEW_WINS")) return QObject::tr("采用新内容（NEW_WINS）");
    if (value == QStringLiteral("MERGE")) return QObject::tr("自动合并（MERGE）");
    if (value == QStringLiteral("MANUAL")) return QObject::tr("待人工确认（MANUAL）");
    return value.isEmpty() ? QObject::tr("未提供处理结果") : value;
}
QString severityText(const QString &value)
{
    if (value == QStringLiteral("low")) return QObject::tr("低（low）");
    if (value == QStringLiteral("medium")) return QObject::tr("中（medium）");
    if (value == QStringLiteral("high")) return QObject::tr("高（high）");
    return value.isEmpty() ? QObject::tr("未提供严重程度") : value;
}
QString readable(const QJsonValue &value)
{
    if (value.isString()) return value.toString();
    if (value.isBool()) return value.toBool() ? QObject::tr("是") : QObject::tr("否");
    if (value.isDouble()) return QString::number(value.toDouble());
    QStringList lines;
    if (value.isObject()) {
        const auto object = value.toObject();
        for (auto it = object.begin(); it != object.end(); ++it)
            lines << it.key() + QStringLiteral(": ") + readable(it.value());
    } else if (value.isArray()) {
        for (const auto &item : value.toArray()) lines << readable(item);
    }
    return lines.join(QStringLiteral("\n"));
}
}
namespace pixiu {
MemoryAudit::MemoryAudit(QWidget *parent, BackendTransport *transport)
    : QWidget(parent), m_transport(transport ? transport : new HttpBackendTransport(this))
{
    m_refreshTimer = new QTimer(this);
    m_refreshTimer->setSingleShot(true);
    m_refreshTimer->setInterval(500);
    connect(m_refreshTimer, &QTimer::timeout, this, [this]() {
        if (m_refreshNeeded && isVisible() && m_pending == Pending::None) refresh(true);
    });
    auto *layout = new QVBoxLayout(this);
    m_mode = new QComboBox(this);
    m_mode->setObjectName(QStringLiteral("auditMode"));
    m_mode->addItems({tr("偏好与历史"), tr("冲突审计")});
    m_scope = new QComboBox(this);
    m_scope->setObjectName(QStringLiteral("auditScope"));
    populateMemoryScopes(m_scope, true);
    m_refresh = new QPushButton(tr("刷新"), this);
    m_refresh->setObjectName(QStringLiteral("auditRefresh"));
    m_extract = new QPushButton(tr("从当前证据提取偏好"), this);
    m_extract->setObjectName(QStringLiteral("auditExtract"));
    auto *toolbar = new QHBoxLayout;
    toolbar->addWidget(m_mode);
    toolbar->addWidget(m_scope);
    toolbar->addStretch();
    toolbar->addWidget(m_refresh);
    layout->addLayout(toolbar);
    layout->addWidget(m_extract);
    m_status = new QLabel(tr("点击刷新加载偏好。提取使用检索来源或最近成功录入的证据。"), this);
    m_status->setObjectName(QStringLiteral("auditStatus"));
    m_status->setTextFormat(Qt::PlainText);
    m_status->setWordWrap(true);
    layout->addWidget(m_status);
    m_records = new QListWidget(this);
    m_records->setObjectName(QStringLiteral("auditRecords"));
    m_records->setWordWrap(true);
    m_records->setAccessibleName(tr("偏好或冲突记录"));
    layout->addWidget(m_records, 1);
    m_details = new QPlainTextEdit(this);
    m_details->setObjectName(QStringLiteral("auditDetails"));
    m_details->setReadOnly(true);
    m_details->setAccessibleName(tr("历史与审计详情"));
    layout->addWidget(m_details, 1);
    connect(m_refresh, &QPushButton::clicked, this, &MemoryAudit::refresh);
    connect(m_mode, QOverload<int>::of(&QComboBox::currentIndexChanged), this, [this]() { refresh(); });
    connect(m_scope, QOverload<int>::of(&QComboBox::currentIndexChanged), this, [this]() { refresh(); });
    connect(m_extract, &QPushButton::clicked, this, [this]() {
        if (m_pending != Pending::None || m_evidenceIds.isEmpty()) return;
        m_pending = Pending::Extract;
        updateControls();
        m_status->setText(tr("正在从 %1 条证据提取偏好…").arg(m_evidenceIds.size()));
        QJsonArray ids;
        for (const auto &id : m_evidenceIds) ids.append(id);
        m_transport->extractPreferences({{QStringLiteral("evidence_ids"), ids}});
    });
    connect(m_transport, &BackendTransport::preferencesListResult, this, [this](const QJsonArray &records) {
        if (m_pending != Pending::Preferences) return;
        m_pending = Pending::None;
        updateControls();
        for (const auto &value : records) {
            const auto record = value.toObject();
            auto *item = new QListWidgetItem(tr("%1 · %2\n%3").arg(record.value("key").toString(),
                record.value("scope").toString(), readable(record.value("value"))), m_records);
            item->setData(Qt::UserRole, record);
        }
        m_status->setText(records.isEmpty() ? tr("此范围暂无偏好。") : tr("选择偏好查看版本历史。"));
        restoreSelection();
    });
    connect(m_transport, &BackendTransport::conflictsResult, this, [this](const QJsonArray &records) {
        if (m_pending != Pending::Conflicts) return;
        m_pending = Pending::None;
        updateControls();
        for (const auto &value : records) {
            const auto record = value.toObject();
            const QString title = record.value("knowledge_title").toString();
            auto *item = new QListWidgetItem(tr("%1\n%2 · %3\n处理结果：%4")
                .arg(title.isEmpty() ? tr("未提供关联记忆标题") : title,
                     record.value("field").toString(), severityText(record.value("severity").toString()),
                     resolutionText(record.value("resolution").toString())), m_records);
            item->setData(Qt::UserRole, record);
        }
        m_status->setText(records.isEmpty() ? tr("暂无冲突记录。") : tr("全部范围的只读审计记录；不提供人工裁决操作。"));
        restoreSelection();
    });
    connect(m_records, &QListWidget::currentItemChanged, this, [this](QListWidgetItem *item) {
        if (!item || m_pending != Pending::None) return;
        const auto record = item->data(Qt::UserRole).toJsonObject();
        m_details->clear();
        if (m_mode->currentIndex() == 1) {
            QString detail = tr("字段：%1\n原内容：\n%2\n新内容：\n%3\n处理结果：%4\n严重程度：%5")
                .arg(record.value("field").toString(), readable(record.value("old_value")),
                     readable(record.value("new_value")), resolutionText(record.value("resolution").toString()),
                     severityText(record.value("severity").toString()));
            const QString title = record.value("knowledge_title").toString();
            if (!title.isEmpty()) detail.prepend(tr("关联记忆：%1\n").arg(title));
            detail += tr("\n\n此处仅展示后端审计记录，不提供裁决或回滚。待人工确认不表示已完成处理。");
            m_details->setPlainText(detail);
            return;
        }
        m_historyId = record.value("id").toString();
        if (m_historyId.isEmpty()) { m_status->setText(tr("此偏好缺少标识，无法读取历史。")); return; }
        m_pending = Pending::History;
        updateControls();
        m_status->setText(tr("正在加载偏好历史…"));
        m_transport->preferenceHistory(m_historyId);
    });
    connect(m_transport, &BackendTransport::preferenceHistoryResult, this, [this](const QJsonObject &result) {
        if (m_pending != Pending::History) return;
        m_pending = Pending::None;
        updateControls();
        if (result.value("id").toString() != m_historyId) {
            m_status->setText(tr("历史响应与所选偏好不一致，请重新选择。"));
            m_records->setCurrentRow(-1);
            return;
        }
        QStringList snapshots;
        for (const auto &value : result.value("history").toArray()) {
            const auto record = value.toObject();
            const auto updated = record.value("updated_at");
            const QString date = updated.isDouble()
                ? QDateTime::fromSecsSinceEpoch(qint64(updated.toDouble())).toString(Qt::ISODate)
                : updated.toString();
            snapshots << tr("版本 %1 · %2\n%3").arg(record.value("version").toInt()).arg(date, readable(record.value("value")));
        }
        m_details->setPlainText(snapshots.isEmpty() ? tr("暂无历史版本。") : snapshots.join(QStringLiteral("\n\n")));
        m_status->setText(tr("%1 · 当前版本 %2").arg(result.value("key").toString()).arg(result.value("current_version").toInt()));
    });
    connect(m_transport, &BackendTransport::preferenceExtractResult, this, [this](const QJsonObject &result) {
        if (m_pending != Pending::Extract) return;
        m_pending = Pending::None;
        updateControls();
        if (!result.value("extracted_preferences").isArray()) {
            m_status->setText(tr("提取响应不完整，无法确认结果。"));
            return;
        }
        m_status->setText(tr("提取返回 %1 条偏好。点击刷新查看当前列表。").arg(result.value("extracted_preferences").toArray().size()));
    });
    connect(m_transport, &BackendTransport::errorOccurred, this, [this](const QString &, const QString &message, const QString &) {
        if (m_pending == Pending::None) return;
        m_pending = Pending::None;
        updateControls();
        m_records->setCurrentRow(-1);
        m_status->setText(tr("操作失败：%1。可刷新列表或重新选择记录重试。").arg(message));
    });
    updateControls();
}
void MemoryAudit::setEvidenceIds(const QStringList &ids)
{
    m_evidenceIds = ids;
    m_evidenceIds.removeAll(QString());
    m_evidenceIds.removeDuplicates();
    updateControls();
}
void MemoryAudit::updateControls()
{
    const bool idle = m_pending == Pending::None;
    m_mode->setEnabled(idle);
    m_scope->setEnabled(idle && m_mode->currentIndex() == 0);
    m_refresh->setEnabled(idle);
    m_records->setEnabled(idle);
    m_extract->setEnabled(idle && m_mode->currentIndex() == 0 && !m_evidenceIds.isEmpty());
    scheduleRefresh();
}
void MemoryAudit::notifyDataChanged()
{
    m_refreshNeeded = true;
    scheduleRefresh();
}
void MemoryAudit::scheduleRefresh()
{
    if (m_refreshNeeded && isVisible() && m_pending == Pending::None && !m_refreshTimer->isActive())
        m_refreshTimer->start();
}
void MemoryAudit::showEvent(QShowEvent *event)
{
    QWidget::showEvent(event);
    scheduleRefresh();
}
void MemoryAudit::restoreSelection()
{
    const QString wanted = m_restoreSelection;
    m_restoreSelection.clear();
    if (wanted.isEmpty()) return;
    for (int row = 0; row < m_records->count(); ++row) {
        if (m_records->item(row)->data(Qt::UserRole).toJsonObject().value("id").toString() == wanted) {
            m_records->setCurrentRow(row);
            return;
        }
    }
}
void MemoryAudit::refresh(bool preserveSelection)
{
    if (m_pending != Pending::None) return;
    m_restoreSelection = preserveSelection && m_records->currentItem()
        ? m_records->currentItem()->data(Qt::UserRole).toJsonObject().value("id").toString() : QString();
    m_refreshNeeded = false;
    m_refreshTimer->stop();
    m_records->clear();
    m_details->clear();
    m_pending = m_mode->currentIndex() == 0 ? Pending::Preferences : Pending::Conflicts;
    updateControls();
    m_status->setText(tr("正在加载…"));
    if (m_pending == Pending::Preferences) m_transport->preferencesList(m_scope->currentData().toString());
    else m_transport->listConflicts();
}
}
