#include "widgets/MonitorCenterDialog.h"

#include "app/MonitorController.h"
#include "app/UiTokens.h"

#include <QCheckBox>
#include <QCoreApplication>
#include <QDateTime>
#include <QDir>
#include <QFileDialog>
#include <QHBoxLayout>
#include <QJsonObject>
#include <QLabel>
#include <QLineEdit>
#include <QListWidget>
#include <QPushButton>
#include <QSignalBlocker>
#include <QTabWidget>
#include <QVBoxLayout>

namespace {
// 匿名命名空间内无法使用成员 tr()，统一走 QCoreApplication::translate
// （与 MemoryPanel.cpp 既有做法一致）。
QString sourceLabel(MonitorSource source)
{
    // 数据源中文名复用控制器单一来源，避免 .ts 双份条目。
    return MonitorController::sourceDisplayName(source);
}

QString sourceHint(MonitorSource source)
{
    switch (source) {
    case MonitorSource::Directory:
        return QCoreApplication::translate(
            "MonitorCenterDialog", "监视下方目录，新文件自动识别入库");
    case MonitorSource::Clipboard:
        return QCoreApplication::translate("MonitorCenterDialog",
                                           "复制较长文本或图片时自动捕获");
    case MonitorSource::Behavior:
        return QCoreApplication::translate(
            "MonitorCenterDialog", "记录常用应用与操作习惯，用于偏好提取");
    case MonitorSource::Screenshot:
        return QCoreApplication::translate("MonitorCenterDialog",
                                           "截屏内容经 OCR 后沉淀为记忆");
    }
    return QString();
}

QString formatLogTime(qint64 ts)
{
    return QDateTime::fromSecsSinceEpoch(ts)
        .toString(QStringLiteral("MM-dd HH:mm"));
}
} // namespace

MonitorCenterDialog::MonitorCenterDialog(MonitorController *controller,
                                         QWidget *parent)
    : QDialog(parent)
    , m_controller(controller)
{
    setWindowTitle(tr("监控中心"));
    resize(460, 420);
    setMinimumSize(400, 360);

    m_tabs = new QTabWidget(this);
    m_tabs->addTab(new QWidget(this), tr("数据源"));
    m_tabs->addTab(new QWidget(this), tr("活动记录"));
    // 活动记录懒加载：首次切到该 Tab 时请求首页分页（防重复由
    // m_remoteLogLoaded 保证）。
    connect(m_tabs, &QTabWidget::currentChanged, this, [this](int index) {
        if (index == 1) {
            requestFirstLogPage();
        }
    });

    // ── Tab1 数据源 ──────────────────────────────────────────────
    QWidget *sourcePage = m_tabs->widget(0);
    QVBoxLayout *sourceLayout = new QVBoxLayout(sourcePage);

    m_masterCheck = new QCheckBox(tr("启用监控（总开关）"), sourcePage);
    m_masterCheck->setObjectName(QStringLiteral("monitorMasterCheck"));
    m_masterCheck->setAccessibleName(tr("监控总开关"));
    connect(m_masterCheck, &QCheckBox::toggled,
            this, &MonitorCenterDialog::onMasterToggled);

    QLabel *hint = new QLabel(
        tr("开启后 PIXIU 将在您指定的范围内静默捕获信息；"
           "可随时暂停，活动记录完整可查。"),
        sourcePage);
    hint->setWordWrap(true);
    hint->setStyleSheet(ui::textStyle(ui::Role::Muted));

    // 离线状态行：远端配置上送失败时提示「离线，仅本地生效」（A-3）。
    m_offlineHint = new QLabel(sourcePage);
    m_offlineHint->setObjectName(QStringLiteral("monitorOfflineHint"));
    m_offlineHint->setStyleSheet(ui::textStyle(ui::Role::Warning));
    m_offlineHint->setVisible(false);

    sourceLayout->addWidget(m_masterCheck);
    sourceLayout->addWidget(hint);
    sourceLayout->addWidget(m_offlineHint);

    for (int i = 0; i < MonitorController::sourceCount(); ++i) {
        const auto source = static_cast<MonitorSource>(i);
        QCheckBox *check = new QCheckBox(sourceLabel(source), sourcePage);
        check->setProperty("monitorSource", i);
        check->setAccessibleName(sourceLabel(source));
        check->setToolTip(sourceHint(source));
        connect(check, &QCheckBox::toggled, this, [this, source](bool on) {
            m_controller->setSourceEnabled(source, on);
            // 面板改动统一经 configEdited 上送（PixiuApp 侧唯一 PUT 触发点）。
            emit configEdited();
        });
        sourceLayout->addWidget(check);
        m_sourceChecks.append(check);
    }

    QLabel *dirTitle = new QLabel(tr("监视目录"), sourcePage);
    m_dirList = new QListWidget(sourcePage);
    m_dirList->setObjectName(QStringLiteral("monitorDirList"));

    m_dirEdit = new QLineEdit(sourcePage);
    m_dirEdit->setObjectName(QStringLiteral("monitorDirEdit"));
    m_dirEdit->setAccessibleName(tr("监视目录路径"));
    m_dirEdit->setPlaceholderText(tr("输入或浏览要监视的目录…"));

    QPushButton *browseButton = new QPushButton(tr("浏览…"), sourcePage);
    browseButton->setObjectName(QStringLiteral("monitorDirBrowse"));
    connect(browseButton, &QPushButton::clicked, this, [this]() {
        const QString dir = QFileDialog::getExistingDirectory(
            this, tr("选择监视目录"), QDir::homePath());
        if (!dir.isEmpty()) {
            m_dirEdit->setText(dir);
        }
    });

    QPushButton *addButton = new QPushButton(tr("添加"), sourcePage);
    addButton->setObjectName(QStringLiteral("monitorDirAdd"));
    connect(addButton, &QPushButton::clicked,
            this, &MonitorCenterDialog::onAddDirectory);

    QPushButton *removeButton = new QPushButton(tr("移除所选"), sourcePage);
    removeButton->setObjectName(QStringLiteral("monitorDirRemove"));
    connect(removeButton, &QPushButton::clicked,
            this, &MonitorCenterDialog::onRemoveDirectory);

    QHBoxLayout *dirEditRow = new QHBoxLayout();
    dirEditRow->addWidget(m_dirEdit, 1);
    dirEditRow->addWidget(browseButton);
    dirEditRow->addWidget(addButton);

    QHBoxLayout *dirRemoveRow = new QHBoxLayout();
    dirRemoveRow->addStretch(1);
    dirRemoveRow->addWidget(removeButton);

    sourceLayout->addWidget(dirTitle);
    sourceLayout->addWidget(m_dirList, 1);
    sourceLayout->addLayout(dirEditRow);
    sourceLayout->addLayout(dirRemoveRow);

    // ── Tab2 活动记录 ────────────────────────────────────────────
    QWidget *logPage = m_tabs->widget(1);
    QVBoxLayout *logLayout = new QVBoxLayout(logPage);
    m_logList = new QListWidget(logPage);
    m_logList->setObjectName(QStringLiteral("monitorLogList"));
    m_logList->setSelectionMode(QAbstractItemView::NoSelection);
    logLayout->addWidget(m_logList);

    QVBoxLayout *root = new QVBoxLayout(this);
    root->addWidget(m_tabs);

    connect(m_controller, &MonitorController::logAppended, this,
            [this](const MonitorLogEntry &entry) {
                m_logList->addItem(
                    QStringLiteral("[%1] %2")
                        .arg(formatLogTime(entry.timestamp), entry.text));
                m_logList->scrollToBottom();
            });
    connect(m_controller, &MonitorController::directoriesChanged, this,
            [this]() { rebuildDirectoryList(); });
    // 外部写入方（托盘/悬浮球菜单直接调用 controller->setEnabled /
    // setSourceEnabled）改变状态时，常驻复用的面板必须实时同步勾选态，
    // 否则会显示陈旧开关。镜像写入用 QSignalBlocker 包裹，局部自证
    // “此处仅做 UI 镜像、不回写控制器”，不依赖控制器等态短路防递归。
    connect(m_controller, &MonitorController::enabledChanged, this,
            [this](bool on) {
                const QSignalBlocker masterBlocker(m_masterCheck);
                m_masterCheck->setChecked(on);
                for (QCheckBox *check : m_sourceChecks) {
                    check->setEnabled(on);
                }
            });
    connect(m_controller, &MonitorController::sourceChanged, this,
            [this](MonitorSource source, bool on) {
                const int index = static_cast<int>(source);
                if (index >= 0 && index < m_sourceChecks.size()) {
                    const QSignalBlocker blocker(m_sourceChecks.at(index));
                    m_sourceChecks.at(index)->setChecked(on);
                }
            });

    // 初始状态回填：用 QSignalBlocker 包裹，明确“此处仅做 UI 镜像、
    // 不回写控制器”——比依赖回填语句与 connect 的相对顺序更稳健。
    {
        const QSignalBlocker masterBlocker(m_masterCheck);
        m_masterCheck->setChecked(m_controller->isEnabled());
        for (int i = 0; i < m_sourceChecks.size(); ++i) {
            const QSignalBlocker blocker(m_sourceChecks.at(i));
            m_sourceChecks.at(i)->setChecked(
                m_controller->isSourceEnabled(static_cast<MonitorSource>(i)));
            m_sourceChecks.at(i)->setEnabled(m_controller->isEnabled());
        }
    }
    rebuildDirectoryList();
    reloadLog();
}

void MonitorCenterDialog::showAndFocus()
{
    show();
    raise();
    activateWindow();
    m_masterCheck->setFocus();
    // 活动记录懒加载：面板打开即请求首页（m_remoteLogLoaded 防重复）。
    requestFirstLogPage();
}

void MonitorCenterDialog::onMasterToggled(bool on)
{
    m_controller->setEnabled(on);
    for (QCheckBox *check : m_sourceChecks) {
        check->setEnabled(on);
    }
    emit configEdited();
}

void MonitorCenterDialog::onAddDirectory()
{
    const QString path = m_dirEdit->text().trimmed();
    if (path.isEmpty()) {
        return;
    }
    QStringList dirs = m_controller->directories();
    dirs << path;
    m_controller->setDirectories(dirs);
    m_dirEdit->clear();
    emit configEdited();
}

void MonitorCenterDialog::onRemoveDirectory()
{
    const int row = m_dirList->currentRow();
    if (row < 0) {
        return;
    }
    QStringList dirs = m_controller->directories();
    if (row >= dirs.size()) {
        return;
    }
    dirs.removeAt(row);
    m_controller->setDirectories(dirs);
    emit configEdited();
}

void MonitorCenterDialog::reloadLog()
{
    m_logList->clear();
    // 本地日志与远端事件去重键相互独立（local 前缀区分），重建时清空
    // 远端去重键，避免残留键挡住后续远端/实时条目。
    m_logKeys.clear();
    const auto entries = m_controller->log();
    for (const MonitorLogEntry &entry : entries) {
        m_logList->addItem(QStringLiteral("[%1] %2")
                               .arg(formatLogTime(entry.timestamp),
                                    entry.text));
        m_logKeys.insert(QStringLiteral("%1|local|%2")
                             .arg(entry.timestamp)
                             .arg(entry.text));
    }
    m_logList->scrollToBottom();
}

void MonitorCenterDialog::rebuildDirectoryList()
{
    m_dirList->clear();
    m_dirList->addItems(m_controller->directories());
}

void MonitorCenterDialog::appendRemoteLog(const QJsonArray &entries)
{
    // 契约 §2：服务端返回「最新在前」。逆序遍历（先追加最旧、最后追加
    // 最新），使列表「底部最新」与本地日志/capture_event 一致——
    // scrollToBottom 自然落在最新条目上。
    for (int i = entries.size() - 1; i >= 0; --i) {
        const QJsonObject entry = entries.at(i).toObject();
        const qint64 ts =
            entry.value(QStringLiteral("ts")).toVariant().toLongLong();
        const QString source =
            entry.value(QStringLiteral("source")).toString();
        const QString summary =
            entry.value(QStringLiteral("summary")).toString();
        QStringList ids;
        const QString evidenceId =
            entry.value(QStringLiteral("evidence_id")).toString();
        const QString knowledgeId =
            entry.value(QStringLiteral("knowledge_id")).toString();
        if (!evidenceId.isEmpty()) {
            ids << evidenceId;
        }
        if (!knowledgeId.isEmpty()) {
            ids << knowledgeId;
        }
        // 「[MM-dd HH:mm] 文案」；无 id 的条目省略 id 部分。
        const QString idsSuffix = ids.isEmpty()
                                      ? QString()
                                      : tr("（%1）").arg(ids.join(tr("、")));
        appendLogLine(ts, source, summary, idsSuffix,
                      ids.join(QStringLiteral("|")));
    }
    m_logList->scrollToBottom();
}

void MonitorCenterDialog::appendCaptureEvent(const QString &source,
                                             const QString &,
                                             const QString &summary,
                                             qint64 ts)
{
    // capture_event 与本地日志同列表渲染；status 不参与显示文案。
    appendLogLine(ts, source, summary, QString(), QString());
    m_logList->scrollToBottom();
}

void MonitorCenterDialog::setOfflineHint(bool offline)
{
    if (!m_offlineHint) {
        return;
    }
    m_offlineHint->setVisible(offline);
    if (offline) {
        m_offlineHint->setText(tr("离线，仅本地生效"));
    }
}

void MonitorCenterDialog::requestFirstLogPage()
{
    if (m_remoteLogLoaded) {
        return;
    }
    m_remoteLogLoaded = true;
    emit logPageRequested(100, 0);
}

void MonitorCenterDialog::appendLogLine(qint64 ts, const QString &source,
                                        const QString &summary,
                                        const QString &idsSuffix,
                                        const QString &idKey)
{
    // 远端分页与实时 WS 可能重复送达同一事件：按键去重，只追加一次。
    // 有 evidence_id/knowledge_id 时键用 ts|id（同 ts/source/summary 的
    // 不同事件不互相误杀）；本地/实时无 id 时保持 ts|source|summary。
    const QString key = idKey.isEmpty()
                            ? QStringLiteral("%1|%2|%3")
                                  .arg(ts)
                                  .arg(source, summary)
                            : QStringLiteral("%1|%2").arg(ts).arg(idKey);
    if (m_logKeys.contains(key)) {
        return;
    }
    m_logKeys.insert(key);
    m_logList->addItem(QStringLiteral("[%1] %2%3")
                           .arg(formatLogTime(ts), summary, idsSuffix));
}
