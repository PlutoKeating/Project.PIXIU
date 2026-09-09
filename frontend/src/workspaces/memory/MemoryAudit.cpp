#include "MemoryAudit.h"
#include "MemoryScopes.h"
#include "MemoryScopeControl.h"
#include "services/HttpBackendTransport.h"
#include <QComboBox>
#include <QDateTime>
#include <QDialog>
#include <QDialogButtonBox>
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
    m_mode->addItems({tr("我的偏好"), tr("需要确认")});
    m_scope = new QComboBox(this);
    m_scope->setObjectName(QStringLiteral("auditScope"));
    populateMemoryScopes(m_scope, true);
    auto *toolbar = new QHBoxLayout;
    toolbar->addWidget(m_mode);
    m_scope->setMaximumWidth(220);
    toolbar->addWidget(m_scope);
    toolbar->addStretch();
    layout->addLayout(toolbar);
    m_status = new QLabel(tr("助手会从日常交流和资料中自动记住你的偏好。"), this);
    m_status->setObjectName(QStringLiteral("auditStatus"));
    m_status->setTextFormat(Qt::PlainText);
    m_status->setWordWrap(true);
    layout->addWidget(m_status);
    m_records = new QListWidget(this);
    m_records->setObjectName(QStringLiteral("auditRecords"));
    m_records->setWordWrap(true);
    m_records->setAccessibleName(tr("偏好或冲突记录"));
    layout->addWidget(m_records, 1);
    m_records->hide();
    m_details = new QPlainTextEdit(this);
    m_details->setObjectName(QStringLiteral("auditDetails"));
    m_details->setReadOnly(true);
    m_details->setAccessibleName(tr("历史与审计详情"));
    layout->addWidget(m_details, 1);
    m_details->hide();
    connect(m_details, &QPlainTextEdit::textChanged, this, [this]() {
        m_details->setVisible(!m_details->toPlainText().isEmpty());
    });
    auto *review = new QPushButton(tr("处理所选冲突"), this);
    review->setObjectName("reviewManualConflict");
    layout->addWidget(review);
    review->hide();
    connect(m_records, &QListWidget::currentItemChanged, review, [review, this](QListWidgetItem *item) {
        const auto record = item ? item->data(Qt::UserRole).toJsonObject() : QJsonObject();
        review->setVisible(m_mode->currentIndex() == 1 && record.value("resolution").toString() == "MANUAL");
    });
    auto *reviewHttp = new HttpBackendTransport(this);
    connect(review, &QPushButton::clicked, this, [=]() {
        auto *row = m_records->currentItem();
        if (m_pending != Pending::None || m_mode->currentIndex() != 1 || !row) return;
        const auto record = row->data(Qt::UserRole).toJsonObject();
        if (record.value("resolution") != "MANUAL") return;
        review->setProperty("conflictId", record.value("id").toString());
        m_pending = Pending::Review; updateControls();
        reviewHttp->reviewConflict(record.value("id").toString());
    });
    connect(reviewHttp, &HttpBackendTransport::conflictReviewResult, this, [=](const QJsonObject &result) {
        QDialog dialog(this);
        dialog.setWindowTitle(tr("确认采用哪份记忆"));
        auto *layout = new QVBoxLayout(&dialog);
        auto *list = new QListWidget(&dialog);
        auto *detail = new QPlainTextEdit(&dialog); detail->setReadOnly(true);
        auto *source = new QPushButton(tr("查看所选版本的原始来源"), &dialog);
        QJsonObject versions;
        for (const auto &value : result.value("candidates").toArray()) {
            const auto entry = value.toObject();
            versions.insert(entry.value("id").toString(), entry.value("version"));
            auto *row = new QListWidgetItem(entry.value("title").toString()
                + tr(" · 版本 %1").arg(entry.value("version").toInt()), list);
            row->setData(Qt::UserRole, entry);
        }
        layout->addWidget(list); layout->addWidget(detail); layout->addWidget(source);
        connect(list, &QListWidget::currentItemChanged, &dialog, [=](QListWidgetItem *row) {
            detail->setPlainText(row ? readable(row->data(Qt::UserRole).toJsonObject().value("body")) : QString());
        });
        connect(source, &QPushButton::clicked, &dialog, [=]() {
            if (!list->currentItem()) return;
            const auto ids = list->currentItem()->data(Qt::UserRole).toJsonObject().value("evidence_ids").toArray();
            if (!ids.isEmpty()) reviewHttp->evidenceDetail(ids.first().toString());
        });
        connect(reviewHttp, &BackendTransport::evidenceDetailResult, &dialog, [=](const QJsonObject &evidence) {
            detail->setPlainText(readable(evidence.value("raw")));
        });
        auto *buttons = new QDialogButtonBox(QDialogButtonBox::Ok | QDialogButtonBox::Cancel, &dialog);
        buttons->button(QDialogButtonBox::Ok)->setText(tr("保留所选版本"));
        layout->addWidget(buttons);
        connect(buttons, &QDialogButtonBox::accepted, &dialog, &QDialog::accept);
        connect(buttons, &QDialogButtonBox::rejected, &dialog, &QDialog::reject);
        dialog.resize(620, 460); list->setCurrentRow(0);
        if (dialog.exec() == QDialog::Accepted && list->currentItem()) {
            m_pending = Pending::Resolve;
            reviewHttp->resolveConflict(review->property("conflictId").toString(),
                {{"keep_id", list->currentItem()->data(Qt::UserRole).toJsonObject().value("id")}, {"versions", versions}});
        } else { m_pending = Pending::None; updateControls(); }
    });
    connect(reviewHttp, &HttpBackendTransport::conflictResolved, this, [=](const QJsonObject &) {
        m_pending = Pending::None; refresh();
    });
    connect(reviewHttp, &BackendTransport::errorOccurred, this, [=](const QString &, const QString &, const QString &) {
        m_pending = Pending::None; updateControls();
        m_status->setText(tr("处理未完成，记忆可能已经变化。请刷新后重新核对。"));
    });
    connect(m_mode, QOverload<int>::of(&QComboBox::currentIndexChanged), this, [this]() { refresh(); });
    connect(m_scope, QOverload<int>::of(&QComboBox::currentIndexChanged), this, [this]() { refresh(); });
    connect(m_transport, &BackendTransport::preferencesListResult, this, [this](const QJsonArray &records) {
        if (m_pending != Pending::Preferences) return;
        trackPreferences(records);
        m_pending = Pending::None;
        updateControls();
        for (const auto &value : records) {
            const auto record = value.toObject();
            auto *item = new QListWidgetItem(tr("%1 · %2\n%3").arg(record.value("key").toString(),
                record.value("scope").toString(), readable(record.value("value"))), m_records);
            item->setData(Qt::UserRole, record);
        }
        m_status->setText(records.isEmpty() ? tr("此范围暂无偏好。") : tr("选择偏好查看版本历史。"));
        m_records->setVisible(m_records->count() > 0);
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
                     (record.value("source") == "manual" ? tr("人工已确认") : resolutionText(record.value("resolution").toString()))), m_records);
            item->setData(Qt::UserRole, record);
        }
        m_status->setText(records.isEmpty() ? tr("暂无冲突记录。") : tr("选择待人工确认的冲突，点击“处理所选冲突”查看并选择保留版本。"));
        m_records->setVisible(m_records->count() > 0);
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
    connect(m_transport, &BackendTransport::errorOccurred, this, [this](const QString &, const QString &message, const QString &) {
        if (m_pending == Pending::None) return;
        m_pending = Pending::None;
        updateControls();
        m_records->setCurrentRow(-1);
        m_status->setText(tr("操作失败：%1。可刷新列表或重新选择记录重试。").arg(message));
    });
    updateControls();
}
void MemoryAudit::trackPreferences(const QJsonArray &records)
{
    const QString scope = m_scope->currentData().toString();
    if (m_baselineScope != scope) {
        m_havePreferenceBaseline = false;
        m_preferenceVersions.clear();
        m_baselineScope = scope;
    }
    QHash<QPair<QString, QString>, int> next;
    int changed = 0;
    for (const auto &value : records) {
        const auto record = value.toObject();
        const auto key = qMakePair(record.value("scope").toString(), record.value("id").toString());
        const int version = record.value("version").toInt(-1);
        if (key.first.isEmpty() || key.second.isEmpty() || version < 1
            || (!scope.isEmpty() && key.first != scope) || next.contains(key)) {
            // An incomplete/ambiguous response cannot establish changes.
            m_havePreferenceBaseline = false;
            m_preferenceVersions.clear();
            return;
        }
        const int previous = m_preferenceVersions.value(key, 0);
        if (m_havePreferenceBaseline && version > previous) ++changed;
        next.insert(key, qMax(version, previous));
    }
    m_preferenceVersions = next; // bounded by the current list, not lifetime history
    m_havePreferenceBaseline = true;
    if (changed > 0) emit preferencesChanged(changed);
}
void MemoryAudit::updateControls()
{
    const bool idle = m_pending == Pending::None;
    m_mode->setEnabled(idle);
    m_scope->setEnabled(idle && m_mode->currentIndex() == 0);
    m_records->setEnabled(idle);
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
    m_records->hide();
    m_details->clear();
    m_pending = m_mode->currentIndex() == 0 ? Pending::Preferences : Pending::Conflicts;
    updateControls();
    m_status->setText(tr("正在加载…"));
    if (m_pending == Pending::Preferences) m_transport->preferencesList(m_scope->currentData().toString());
    else m_transport->listConflicts();
}
}
