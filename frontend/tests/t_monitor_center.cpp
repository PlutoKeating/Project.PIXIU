#include <QCheckBox>
#include <QDateTime>
#include <QJsonArray>
#include <QJsonObject>
#include <QLabel>
#include <QLineEdit>
#include <QListWidget>
#include <QPushButton>
#include <QSettings>
#include <QSignalSpy>
#include <QTabWidget>
#include <QTemporaryDir>
#include <QTest>

#include <algorithm>

#include "app/AppSettings.h"
#include "app/MonitorController.h"
#include "widgets/MonitorCenterDialog.h"

// 监控中心面板：主开关联动源开关、目录增删同步控制器、活动记录渲染。
class TestMonitorCenter : public QObject
{
    Q_OBJECT

private slots:
    void initTestCase();
    void masterSwitchGatesSourceChecks();
    void sourceCheckWritesToController();
    void addAndRemoveDirectory();
    void logTabRendersEntries();
    void externalPauseSyncsOpenDialog();
    void appendRemoteLogRendersServerEntries();
    void offlineHintShownWhenSet();
    void captureEventAppendsToLogOnce();
    void dialogMutationEmitsConfigEdited();
    void cleanupTestCase();

private:
    QTemporaryDir m_tempDir;
};

void TestMonitorCenter::initTestCase()
{
    QVERIFY(m_tempDir.isValid());
    qApp->setOrganizationName(QStringLiteral("PixiuTests"));
    qApp->setApplicationName(QStringLiteral("monitor_center"));
    QSettings::setDefaultFormat(QSettings::IniFormat);
    QSettings::setPath(QSettings::IniFormat, QSettings::UserScope,
                       m_tempDir.path());
}

static QCheckBox *masterCheck(const MonitorCenterDialog &dialog)
{
    return dialog.findChild<QCheckBox *>(QStringLiteral("monitorMasterCheck"));
}

static QList<QCheckBox *> sourceChecks(const MonitorCenterDialog &dialog)
{
    QList<QCheckBox *> found;
    const auto all = dialog.findChildren<QCheckBox *>();
    for (QCheckBox *box : all) {
        if (box->property("monitorSource").isValid()) {
            found << box;
        }
    }
    std::sort(found.begin(), found.end(),
              [](QCheckBox *a, QCheckBox *b) {
                  return a->property("monitorSource").toInt()
                         < b->property("monitorSource").toInt();
              });
    return found;
}

void TestMonitorCenter::masterSwitchGatesSourceChecks()
{
    // 隔离：清除前序用例在同一配置文件中持久化的开关状态。
    {
        QSettings raw;
        raw.clear();
    }
    AppSettings settings;
    MonitorController controller(&settings);
    MonitorCenterDialog dialog(&controller);
    dialog.show();

    masterCheck(dialog)->setChecked(true);
    for (QCheckBox *box : sourceChecks(dialog)) {
        QVERIFY(box->isEnabled());
    }
    masterCheck(dialog)->setChecked(false);
    for (QCheckBox *box : sourceChecks(dialog)) {
        QVERIFY(!box->isEnabled());
    }
    QVERIFY(controller.isEnabled() == false);
}

void TestMonitorCenter::sourceCheckWritesToController()
{
    // 隔离：确保 setEnabled(true) 从关闭态出发、能真实产生状态变更。
    {
        QSettings raw;
        raw.clear();
    }
    AppSettings settings;
    MonitorController controller(&settings);
    controller.setEnabled(true);
    MonitorCenterDialog dialog(&controller);
    dialog.show();

    sourceChecks(dialog).at(int(MonitorSource::Clipboard))->setChecked(true);
    QVERIFY(controller.isSourceEnabled(MonitorSource::Clipboard));
}

void TestMonitorCenter::addAndRemoveDirectory()
{
    // 隔离：确保目录清单从空列表出发。
    {
        QSettings raw;
        raw.clear();
    }
    AppSettings settings;
    MonitorController controller(&settings);
    MonitorCenterDialog dialog(&controller);
    dialog.show();

    QTest::keyClicks(
        dialog.findChild<QLineEdit *>(QStringLiteral("monitorDirEdit")),
        QStringLiteral("/tmp/pixiu-watch"));
    QTest::mouseClick(
        dialog.findChild<QPushButton *>(QStringLiteral("monitorDirAdd")),
        Qt::LeftButton);
    QCOMPARE(controller.directories().size(), 1);

    QListWidget *list =
        dialog.findChild<QListWidget *>(QStringLiteral("monitorDirList"));
    QVERIFY(list != nullptr);
    list->setCurrentRow(0);
    QTest::mouseClick(
        dialog.findChild<QPushButton *>(QStringLiteral("monitorDirRemove")),
        Qt::LeftButton);
    QCOMPARE(controller.directories().size(), 0);
}

void TestMonitorCenter::logTabRendersEntries()
{
    // 隔离：清除前序用例持久化的 enabled=true，否则 setEnabled(true)
    // 为空操作、不会产生“监控已开启”日志条目。
    {
        QSettings raw;
        raw.clear();
    }
    AppSettings settings;
    MonitorController controller(&settings);
    controller.setEnabled(true);   // 产生一条“监控已开启”日志
    MonitorCenterDialog dialog(&controller);
    dialog.show();

    QTabWidget *tabs = dialog.findChild<QTabWidget *>();
    QVERIFY(tabs != nullptr);
    tabs->setCurrentIndex(1);
    QListWidget *logList =
        dialog.findChild<QListWidget *>(QStringLiteral("monitorLogList"));
    QVERIFY(logList != nullptr);
    QVERIFY(logList->count() >= 1);
}

void TestMonitorCenter::externalPauseSyncsOpenDialog()
{
    // 外部写入方（托盘/悬浮球直接调 controller->setEnabled）翻转总闸时，
    // 常驻复用、已打开的监控中心面板必须实时同步勾选态与源开关可用性，
    // 不允许显示陈旧状态。
    {
        QSettings raw;
        raw.clear();
    }
    AppSettings settings;
    MonitorController controller(&settings);
    controller.setEnabled(true);
    MonitorCenterDialog dialog(&controller);   // 打开时即处于已启用态
    dialog.show();
    QVERIFY(masterCheck(dialog)->isChecked());
    for (QCheckBox *box : sourceChecks(dialog)) {
        QVERIFY(box->isEnabled());
    }

    controller.setEnabled(false);
    QVERIFY(!masterCheck(dialog)->isChecked());
    for (QCheckBox *box : sourceChecks(dialog)) {
        QVERIFY(!box->isEnabled());
    }

    // 反向恢复：重新开启后勾选与源开关使能一并还原。
    controller.setEnabled(true);
    QVERIFY(masterCheck(dialog)->isChecked());
    for (QCheckBox *box : sourceChecks(dialog)) {
        QVERIFY(box->isEnabled());
    }

    // sourceChanged 镜像：外部直接翻转单个源开关时，
    // 已打开面板的对应源复选框必须同步勾选。
    controller.setSourceEnabled(MonitorSource::Clipboard, true);
    QVERIFY(
        sourceChecks(dialog).at(int(MonitorSource::Clipboard))->isChecked());
}

void TestMonitorCenter::appendRemoteLogRendersServerEntries()
{
    // A-3：服务端分页记录（{ts,source,status,summary,evidence_id,
    // knowledge_id}）渲染到活动记录列表；显示「[MM-dd HH:mm] 文案」，
    // 无 id 的条目省略 id 部分。
    {
        QSettings raw;
        raw.clear();
    }
    AppSettings settings;
    MonitorController controller(&settings);
    MonitorCenterDialog dialog(&controller);
    dialog.show();

    QTabWidget *tabs = dialog.findChild<QTabWidget *>();
    QVERIFY(tabs != nullptr);
    tabs->setCurrentIndex(1);
    QListWidget *logList =
        dialog.findChild<QListWidget *>(QStringLiteral("monitorLogList"));
    QVERIFY(logList != nullptr);
    const int before = logList->count();

    QJsonArray entries;
    entries.append(QJsonObject{
        {QStringLiteral("ts"), 1756080000},
        {QStringLiteral("source"), QStringLiteral("directory")},
        {QStringLiteral("status"), QStringLiteral("ingested")},
        {QStringLiteral("summary"), QStringLiteral("记住文件 支出清单.xlsx")},
        {QStringLiteral("evidence_id"), QStringLiteral("evd_01")},
        {QStringLiteral("knowledge_id"), QStringLiteral("knw_02")},
    });
    // 无 evidence_id / knowledge_id：省略 id 部分（如 ignored / state_changed）。
    entries.append(QJsonObject{
        {QStringLiteral("ts"), 1756080060},
        {QStringLiteral("source"), QStringLiteral("system")},
        {QStringLiteral("status"), QStringLiteral("state_changed")},
        {QStringLiteral("summary"), QStringLiteral("监控配置已更新")},
    });

    dialog.appendRemoteLog(entries);

    QCOMPARE(logList->count(), before + 2);
    const QString firstTime = QDateTime::fromSecsSinceEpoch(1756080000)
                                  .toString(QStringLiteral("MM-dd HH:mm"));
    QCOMPARE(logList->item(before)->text(),
             QStringLiteral("[%1] 记住文件 支出清单.xlsx（evd_01、knw_02）")
                 .arg(firstTime));
    const QString secondTime = QDateTime::fromSecsSinceEpoch(1756080060)
                                   .toString(QStringLiteral("MM-dd HH:mm"));
    QCOMPARE(logList->item(before + 1)->text(),
             QStringLiteral("[%1] 监控配置已更新").arg(secondTime));
}

void TestMonitorCenter::offlineHintShownWhenSet()
{
    // A-3：配置上送失败后面板状态行提示「离线，仅本地生效」，恢复后隐藏。
    {
        QSettings raw;
        raw.clear();
    }
    AppSettings settings;
    MonitorController controller(&settings);
    MonitorCenterDialog dialog(&controller);
    dialog.show();

    QLabel *hint = dialog.findChild<QLabel *>(
        QStringLiteral("monitorOfflineHint"));
    QVERIFY(hint != nullptr);
    QVERIFY(!hint->isVisible());

    dialog.setOfflineHint(true);
    QVERIFY(hint->isVisible());
    QCOMPARE(hint->text(), QStringLiteral("离线，仅本地生效"));

    dialog.setOfflineHint(false);
    QVERIFY(!hint->isVisible());
}

void TestMonitorCenter::captureEventAppendsToLogOnce()
{
    // A-3：capture_event 实时追加与本地日志同列表；同源重复事件
    // （远端分页与实时 WS 可能重复送达）只渲染一次。
    {
        QSettings raw;
        raw.clear();
    }
    AppSettings settings;
    MonitorController controller(&settings);
    MonitorCenterDialog dialog(&controller);
    dialog.show();

    QTabWidget *tabs = dialog.findChild<QTabWidget *>();
    QVERIFY(tabs != nullptr);
    tabs->setCurrentIndex(1);
    QListWidget *logList =
        dialog.findChild<QListWidget *>(QStringLiteral("monitorLogList"));
    QVERIFY(logList != nullptr);
    const int before = logList->count();

    dialog.appendCaptureEvent(QStringLiteral("clipboard"),
                              QStringLiteral("ingested"),
                              QStringLiteral("记住剪贴板内容"), 1756080000);
    dialog.appendCaptureEvent(QStringLiteral("clipboard"),
                              QStringLiteral("ingested"),
                              QStringLiteral("记住剪贴板内容"), 1756080000);
    QCOMPARE(logList->count(), before + 1);
    const QString time = QDateTime::fromSecsSinceEpoch(1756080000)
                             .toString(QStringLiteral("MM-dd HH:mm"));
    QCOMPARE(logList->item(before)->text(),
             QStringLiteral("[%1] 记住剪贴板内容").arg(time));
}

void TestMonitorCenter::dialogMutationEmitsConfigEdited()
{
    // A-3：面板任一配置改动（主开关/源开关/目录增删）触发 configEdited
    // 信号一次——PixiuApp 以此为唯一 PUT 上送点，防止重复上送。
    {
        QSettings raw;
        raw.clear();
    }
    AppSettings settings;
    MonitorController controller(&settings);
    MonitorCenterDialog dialog(&controller);
    dialog.show();
    QSignalSpy editedSpy(&dialog, &MonitorCenterDialog::configEdited);

    masterCheck(dialog)->setChecked(true);
    QCOMPARE(editedSpy.count(), 1);
    sourceChecks(dialog).at(int(MonitorSource::Clipboard))->setChecked(true);
    QCOMPARE(editedSpy.count(), 2);

    QTest::keyClicks(
        dialog.findChild<QLineEdit *>(QStringLiteral("monitorDirEdit")),
        QStringLiteral("/tmp/pixiu-watch"));
    QTest::mouseClick(
        dialog.findChild<QPushButton *>(QStringLiteral("monitorDirAdd")),
        Qt::LeftButton);
    QCOMPARE(editedSpy.count(), 3);

    QListWidget *dirList =
        dialog.findChild<QListWidget *>(QStringLiteral("monitorDirList"));
    dirList->setCurrentRow(0);
    QTest::mouseClick(
        dialog.findChild<QPushButton *>(QStringLiteral("monitorDirRemove")),
        Qt::LeftButton);
    QCOMPARE(editedSpy.count(), 4);
}

void TestMonitorCenter::cleanupTestCase()
{
    AppSettings settings;
    settings.sync();
}

QTEST_MAIN(TestMonitorCenter)
#include "t_monitor_center.moc"
