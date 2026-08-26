#include <QCheckBox>
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

void TestMonitorCenter::cleanupTestCase()
{
    AppSettings settings;
    settings.sync();
}

QTEST_MAIN(TestMonitorCenter)
#include "t_monitor_center.moc"
