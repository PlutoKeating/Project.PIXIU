#include "widgets/MonitorCenterDialog.h"

#include "app/MonitorController.h"
#include "app/UiTokens.h"

#include <QCheckBox>
#include <QCoreApplication>
#include <QDateTime>
#include <QDir>
#include <QFileDialog>
#include <QHBoxLayout>
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

    sourceLayout->addWidget(m_masterCheck);
    sourceLayout->addWidget(hint);

    for (int i = 0; i < MonitorController::sourceCount(); ++i) {
        const auto source = static_cast<MonitorSource>(i);
        QCheckBox *check = new QCheckBox(sourceLabel(source), sourcePage);
        check->setProperty("monitorSource", i);
        check->setAccessibleName(sourceLabel(source));
        check->setToolTip(sourceHint(source));
        connect(check, &QCheckBox::toggled, this, [this, source](bool on) {
            m_controller->setSourceEnabled(source, on);
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
    // 否则会显示陈旧开关。回发的 toggled 由控制器等态短路吸收，不会递归。
    connect(m_controller, &MonitorController::enabledChanged, this,
            [this](bool on) {
                m_masterCheck->setChecked(on);
                for (QCheckBox *check : m_sourceChecks) {
                    check->setEnabled(on);
                }
            });
    connect(m_controller, &MonitorController::sourceChanged, this,
            [this](MonitorSource source, bool on) {
                const int index = static_cast<int>(source);
                if (index >= 0 && index < m_sourceChecks.size()) {
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
}

void MonitorCenterDialog::onMasterToggled(bool on)
{
    m_controller->setEnabled(on);
    for (QCheckBox *check : m_sourceChecks) {
        check->setEnabled(on);
    }
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
}

void MonitorCenterDialog::reloadLog()
{
    m_logList->clear();
    const auto entries = m_controller->log();
    for (const MonitorLogEntry &entry : entries) {
        m_logList->addItem(QStringLiteral("[%1] %2")
                               .arg(formatLogTime(entry.timestamp),
                                    entry.text));
    }
    m_logList->scrollToBottom();
}

void MonitorCenterDialog::rebuildDirectoryList()
{
    m_dirList->clear();
    m_dirList->addItems(m_controller->directories());
}
