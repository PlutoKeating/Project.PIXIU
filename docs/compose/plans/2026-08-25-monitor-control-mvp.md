# 监控掌控层 MVP（批次①）Implementation Plan

> 2026-09-06 代码复核：监控配置、目录/行为采集和 HTTP/WS/UI 已接通；图片 OCR 需要另行可用的原生扩展，剪贴板/截图开关不等于采集器已实现。当前服务为 systemd --user。
> 下文实施步骤、旧接口草图和测试数字保留作阶段历史，不作为当前操作手册；当前契约见 docs/API.md，发布见 docs/DELIVERY_PLAN.md。

> **For agentic workers:** REQUIRED SUB-SKILL: Use compose:subagent (recommended) or compose:execute to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 PIXIU 前端建立「被动监控」的掌控层：监控中心面板（数据源开关矩阵 + 目录清单 + 活动记录）、全局暂停开关（托盘/悬浮球/设置三入口）、连接状态旁的监控状态徽标，全部状态本地持久化；同时产出批次②所需的跨模块 `/monitor/*` API 契约需求单。

**Architecture:** 新增 `MonitorController`（QObject）作为监控状态的单一事实来源——全局开关、四类数据源开关、目录清单经既有 `AppSettings`(QSettings) 持久化，本地活动日志内存维护并以信号广播。新增 `MonitorCenterDialog` 双 Tab 面板读写该控制器。`PixiuApp` 负责把托盘、悬浮球右键菜单、设置对话框的新入口统一接到控制器。真实数据采集器（目录/剪贴板/行为/截图）与远端日志属批次②③，由 `MONITOR_API_REQUIREMENTS.md` 契约先行约束。

**Tech Stack:** C++17 · Qt5 Widgets · QtTest(offscreen) · CMake/Ninja

## Global Constraints

- 只允许修改 `frontend/` 下文件（AGENTS.md §1.3 Module A 铁律）；后端改动留待批次②单独授权。
- 所有用户可见文案必须经 `tr()` 包装（项目 i18n 规范），中文为源文本。
- UI 颜色一律取 palette 角色 / `ui::UiTokens`，禁止硬编码色值。
- 危险操作语义不回归；新对话框 Esc=取消、默认按钮语义明确。
- 测试平台 `QT_QPA_PLATFORM=offscreen`；offscreen 下窗口激活断言需跳过（参照 `t_app_navigation.cpp:121` 的平台判断写法）。
- 提交信息带模块前缀 `feat(frontend):` / `test(frontend):` / `docs(frontend):`，一个逻辑变更一个提交，禁止 push。
- 构建命令：`cmake -S frontend -B build/frontend -DPIXIU_HAVE_KYSDK=OFF -G Ninja && cmake --build build/frontend -j`；测试：`QT_QPA_PLATFORM=offscreen ctest --test-dir build/frontend --output-on-failure`。

---

### Task 1: AppSettings 键位扩展 + MonitorController

**Covers:** 掌控层·监控状态单一事实来源（全局开关/源开关/目录清单/本地日志）

**Files:**
- Modify: `frontend/src/app/AppSettings.h`
- Create: `frontend/src/app/MonitorController.h`
- Create: `frontend/src/app/MonitorController.cpp`
- Test: `frontend/tests/t_monitor_controller.cpp`
- Modify: `frontend/CMakeLists.txt`

**Interfaces:**
- Consumes: `AppSettings::value/setValue/sync`（已存在）
- Produces:
  - `enum class MonitorSource { Directory, Clipboard, Behavior, Screenshot }`
  - `struct MonitorLogEntry { qint64 timestamp; QString text; }`
  - `class MonitorController : QObject` — `isEnabled()`, `isSourceEnabled(MonitorSource)`, `directories()`, `log()`, `setEnabled(bool)`, `setSourceEnabled(MonitorSource,bool)`, `setDirectories(QStringList)`, `appendLog(QString)`；信号 `enabledChanged(bool)`, `sourceChanged(MonitorSource,bool)`, `directoriesChanged(QStringList)`, `logAppended(MonitorLogEntry)`
  - `AppSettings::keyMonitorEnabled` = `"app/monitor/enabled"`、`keyMonitorSourcePrefix` = `"app/monitor/source/"`、`keyMonitorDirectories` = `"app/monitor/directories"`

- [ ] **Step 1: 在 AppSettings.h 追加三个键**

```cpp
    static inline const QString keyMonitorEnabled =
        QStringLiteral("app/monitor/enabled");
    static inline const QString keyMonitorSourcePrefix =
        QStringLiteral("app/monitor/source/");
    static inline const QString keyMonitorDirectories =
        QStringLiteral("app/monitor/directories");
```

- [ ] **Step 2: 写失败测试 frontend/tests/t_monitor_controller.cpp**

```cpp
#include <QSignalSpy>
#include <QTemporaryDir>
#include <QTest>

#include "app/AppSettings.h"
#include "app/MonitorController.h"

// MonitorController：默认态、开关持久化、目录清单、本地活动日志。
class TestMonitorController : public QObject
{
    Q_OBJECT

private slots:
    void initTestCase();
    void defaultsAreOff();
    void enablePersistsAcrossInstances();
    void sourceTogglePersistsAndEmits();
    void directoriesRoundTrip();
    void logRecordsToggles();
    void cleanupTestCase();

private:
    QTemporaryDir m_tempDir;
};

void TestMonitorController::initTestCase()
{
    QVERIFY(m_tempDir.isValid());
    qApp->setOrganizationName(QStringLiteral("PixiuTests"));
    qApp->setApplicationName(QStringLiteral("monitor_controller"));
    QSettings::setDefaultFormat(QSettings::IniFormat);
    QSettings::setPath(QSettings::IniFormat, QSettings::UserScope,
                       m_tempDir.path());
}

void TestMonitorController::defaultsAreOff()
{
    MonitorController controller(new AppSettings(this));
    QVERIFY(!controller.isEnabled());
    for (int i = 0; i < 4; ++i) {
        QVERIFY(!controller.isSourceEnabled(static_cast<MonitorSource>(i)));
    }
    QVERIFY(controller.directories().isEmpty());
    QCOMPARE(controller.log().size(), 0);
}

void TestMonitorController::enablePersistsAcrossInstances()
{
    {
        AppSettings settings;
        MonitorController controller(&settings);
        QSignalSpy spy(&controller, &MonitorController::enabledChanged);
        controller.setEnabled(true);
        QCOMPARE(spy.count(), 1);
        QCOMPARE(spy.takeFirst().at(0).toBool(), true);
    }
    AppSettings settings;
    MonitorController reloaded(&settings);
    QVERIFY(reloaded.isEnabled());
    QCOMPARE(reloaded.log().size(), 0); // 日志不持久化，重启从零开始
}

void TestMonitorController::sourceTogglePersistsAndEmits()
{
    {
        AppSettings settings;
        MonitorController controller(&settings);
        controller.setEnabled(true);
        QSignalSpy spy(&controller, &MonitorController::sourceChanged);
        controller.setSourceEnabled(MonitorSource::Directory, true);
        QCOMPARE(spy.count(), 1);
    }
    AppSettings settings;
    MonitorController reloaded(&settings);
    QVERIFY(reloaded.isSourceEnabled(MonitorSource::Directory));
    QVERIFY(!reloaded.isSourceEnabled(MonitorSource::Clipboard));
}

void TestMonitorController::directoriesRoundTrip()
{
    AppSettings settings;
    MonitorController controller(&settings);
    QSignalSpy spy(&controller, &MonitorController::directoriesChanged);
    controller.setDirectories({QStringLiteral("/home/u/Downloads"),
                               QStringLiteral("/home/u/wxfiles")});
    QCOMPARE(spy.count(), 1);
    QCOMPARE(controller.directories().size(), 2);

    AppSettings settings2;
    MonitorController reloaded(&settings2);
    QCOMPARE(reloaded.directories().size(), 2);
    QCOMPARE(reloaded.directories().first(),
             QStringLiteral("/home/u/Downloads"));
}

void TestMonitorController::logRecordsToggles()
{
    AppSettings settings;
    MonitorController controller(&settings);
    controller.setEnabled(true);
    controller.setSourceEnabled(MonitorSource::Clipboard, true);
    controller.appendLog(QStringLiteral("手动条目"));
    QCOMPARE(controller.log().size(), 3);
    QVERIFY(controller.log().last().text ==
            QStringLiteral("手动条目"));
    // 开关产生的日志时间戳有效
    QVERIFY(controller.log().first().timestamp > 0);
}

void TestMonitorController::cleanupTestCase()
{
    AppSettings settings;
    settings.sync();
}

QTEST_MAIN(TestMonitorController)
#include "t_monitor_controller.moc"
```

- [ ] **Step 3: 运行确认失败**

Run: `cmake -S frontend -B build/frontend -DPIXIU_HAVE_KYSDK=OFF -G Ninja && cmake --build build/frontend -j && QT_QPA_PLATFORM=offscreen ./build/frontend/t_monitor_controller`
Expected: 编译失败 `MonitorController.h: No such file`

- [ ] **Step 4: 实现 MonitorController.h / .cpp**

`MonitorController.h`：

```cpp
#ifndef PIXIU_MONITOR_CONTROLLER_H
#define PIXIU_MONITOR_CONTROLLER_H

#include <QObject>
#include <QString>
#include <QStringList>
#include <QVector>

class AppSettings;

// 监控数据源种类。批次①只承载配置状态；真实采集器在批次②接入。
enum class MonitorSource
{
    Directory,   // 目录文件监视
    Clipboard,   // 剪贴板捕获
    Behavior,    // 应用使用行为
    Screenshot,  // 截屏识别
};

struct MonitorLogEntry
{
    qint64 timestamp = 0;  // Unix 秒
    QString text;
};

// 监控状态控制器：全局开关 + 数据源开关 + 监视目录清单 + 本地活动日志。
//
// 批次①为纯本地实现：状态经 AppSettings 持久化；活动日志只记录本机状态
// 变更且不持久化（重启清零）。真实捕获事件流与远端日志查询由
// frontend/docs/MONITOR_API_REQUIREMENTS.md 定义的 /monitor/* 契约在
// 批次②替换/补充。
class MonitorController : public QObject
{
    Q_OBJECT

public:
    explicit MonitorController(AppSettings *settings,
                               QObject *parent = nullptr);

    bool isEnabled() const { return m_enabled; }
    bool isSourceEnabled(MonitorSource source) const;
    QStringList directories() const { return m_directories; }

    // 全局总闸：关闭时所有数据源停止捕获（状态各自保留，恢复总闸即还原）。
    void setEnabled(bool on);
    void setSourceEnabled(MonitorSource source, bool on);
    void setDirectories(const QStringList &dirs);

    QVector<MonitorLogEntry> log() const { return m_log; }
    void appendLog(const QString &text);

    static int sourceCount() { return 4; }
    static const char *sourceKey(MonitorSource source);  // 设置键后缀

signals:
    void enabledChanged(bool on);
    void sourceChanged(MonitorSource source, bool on);
    void directoriesChanged(const QStringList &dirs);
    void logAppended(const MonitorLogEntry &entry);

private:
    void load();

    AppSettings *m_settings = nullptr;
    bool m_enabled = false;
    bool m_sources[4] = {false, false, false, false};
    QStringList m_directories;
    QVector<MonitorLogEntry> m_log;
};

#endif // PIXIU_MONITOR_CONTROLLER_H
```

`MonitorController.cpp`：

```cpp
#include "app/MonitorController.h"

#include "app/AppSettings.h"

#include <QDateTime>

namespace {
MonitorLogEntry makeEntry(const QString &text)
{
    MonitorLogEntry entry;
    entry.timestamp = QDateTime::currentSecsSinceEpoch();
    entry.text = text;
    return entry;
}
} // namespace

const char *MonitorController::sourceKey(MonitorSource source)
{
    switch (source) {
    case MonitorSource::Directory: return "directory";
    case MonitorSource::Clipboard: return "clipboard";
    case MonitorSource::Behavior:  return "behavior";
    case MonitorSource::Screenshot: return "screenshot";
    }
    return "unknown";
}

MonitorController::MonitorController(AppSettings *settings, QObject *parent)
    : QObject(parent)
    , m_settings(settings)
{
    load();
}

bool MonitorController::isSourceEnabled(MonitorSource source) const
{
    return m_sources[static_cast<int>(source)];
}

void MonitorController::load()
{
    m_enabled = m_settings->value(AppSettings::keyMonitorEnabled, false)
                    .toBool();
    for (int i = 0; i < sourceCount(); ++i) {
        const QString key = AppSettings::keyMonitorSourcePrefix
                            + QLatin1String(sourceKey(static_cast<MonitorSource>(i)));
        m_sources[i] = m_settings->value(key, false).toBool();
    }
    m_directories = m_settings
                        ->value(AppSettings::keyMonitorDirectories)
                        .toStringList();
}

void MonitorController::setEnabled(bool on)
{
    if (m_enabled == on) {
        return;
    }
    m_enabled = on;
    m_settings->setValue(AppSettings::keyMonitorEnabled, on);
    m_settings->sync();
    appendLog(on ? QObject::tr("监控已开启")
                 : QObject::tr("监控已暂停"));
    emit enabledChanged(on);
}

void MonitorController::setSourceEnabled(MonitorSource source, bool on)
{
    const int index = static_cast<int>(source);
    if (m_sources[index] == on) {
        return;
    }
    m_sources[index] = on;
    const QString key = AppSettings::keyMonitorSourcePrefix
                        + QLatin1String(sourceKey(source));
    m_settings->setValue(key, on);
    m_settings->sync();
    emit sourceChanged(source, on);
}

void MonitorController::setDirectories(const QStringList &dirs)
{
    QStringList cleaned;
    for (const QString &dir : dirs) {
        const QString trimmed = dir.trimmed();
        if (!trimmed.isEmpty() && !cleaned.contains(trimmed)) {
            cleaned << trimmed;
        }
    }
    if (cleaned == m_directories) {
        return;
    }
    m_directories = cleaned;
    m_settings->setValue(AppSettings::keyMonitorDirectories, m_directories);
    m_settings->sync();
    emit directoriesChanged(m_directories);
}

void MonitorController::appendLog(const QString &text)
{
    const MonitorLogEntry entry = makeEntry(text);
    m_log.append(entry);
    emit logAppended(entry);
}
```

- [ ] **Step 5: 注册构建目标**

`frontend/CMakeLists.txt` 主执行列表 `add_executable(pixiu-frontend ...)` 中追加：

```cmake
    src/app/MonitorController.h
    src/app/MonitorController.cpp
```

测试区块追加：

```cmake
    add_executable(t_monitor_controller
        tests/t_monitor_controller.cpp
        src/app/AppSettings.h
        src/app/AppSettings.cpp
        src/app/MonitorController.h
        src/app/MonitorController.cpp
    )
    target_include_directories(t_monitor_controller PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/src)
    target_link_libraries(t_monitor_controller PRIVATE Qt5::Test Qt5::Core)
    add_test(NAME monitor_controller COMMAND t_monitor_controller)
```

并在文件末尾已有的 `set_tests_properties(... PROPERTIES ENVIRONMENT "QT_QPA_PLATFORM=offscreen")` 列表末尾追加 `monitor_controller`。

- [ ] **Step 6: 运行测试通过**

Run: `cmake --build build/frontend -j && QT_QPA_PLATFORM=offscreen ctest --test-dir build/frontend -R monitor_controller --output-on-failure`
Expected: `1/1 Test #.. monitor_controller ........ Passed`

- [ ] **Step 7: Commit**

```bash
git add frontend/src/app/AppSettings.h frontend/src/app/MonitorController.h \
        frontend/src/app/MonitorController.cpp frontend/tests/t_monitor_controller.cpp \
        frontend/CMakeLists.txt
git commit -m "feat(frontend): add monitor controller with persistent switches"
```

---

### Task 2: MonitorCenterDialog 监控中心面板

**Covers:** 掌控层·监控中心设置页（数据源开关矩阵 + 目录管理 + 活动记录视图）

**Files:**
- Create: `frontend/src/widgets/MonitorCenterDialog.h`
- Create: `frontend/src/widgets/MonitorCenterDialog.cpp`
- Test: `frontend/tests/t_monitor_center.cpp`
- Modify: `frontend/CMakeLists.txt`

**Interfaces:**
- Consumes: Task 1 的 `MonitorController` 全部接口；`ui::Spacing`/`ui::Font`（UiTokens.h）
- Produces:
  - `class MonitorCenterDialog : QDialog` — 构造注入 `MonitorController*`；`showAndFocus()`；无对外信号（直接读写控制器）

- [ ] **Step 1: 写失败测试 frontend/tests/t_monitor_center.cpp**

```cpp
#include <QCheckBox>
#include <QListWidget>
#include <QPushButton>
#include <QSignalSpy>
#include <QTabWidget>
#include <QTemporaryDir>
#include <QTest>

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

void TestMonitorCenter::cleanupTestCase()
{
    AppSettings settings;
    settings.sync();
}

QTEST_MAIN(TestMonitorCenter)
#include "t_monitor_center.moc"
```

- [ ] **Step 2: 运行确认失败（头文件不存在导致编译失败）**

Run: `cmake --build build/frontend -j 2>&1 | tail -3`
Expected: `MonitorCenterDialog.h: No such file or directory`

- [ ] **Step 3: 实现 MonitorCenterDialog.h**

```cpp
#ifndef PIXIU_MONITOR_CENTER_DIALOG_H
#define PIXIU_MONITOR_CENTER_DIALOG_H

#include <QDialog>
#include <QList>

class QCheckBox;
class QLineEdit;
class QListWidget;
class QTabWidget;

class MonitorController;

// 监控中心：「被动监控」的用户掌控面。
//   Tab1 数据源 —— 主开关 + 四类数据源开关矩阵 + 监视目录清单（增删）；
//   Tab2 活动记录 —— 只读日志列表（当前为本机状态变更，批次②接远端事件）。
// 直接读写注入的 MonitorController，不持有独立状态。
class MonitorCenterDialog : public QDialog
{
    Q_OBJECT

public:
    explicit MonitorCenterDialog(MonitorController *controller,
                                 QWidget *parent = nullptr);

    void showAndFocus();

private slots:
    void onMasterToggled(bool on);
    void onAddDirectory();
    void onRemoveDirectory();
    void reloadLog();

private:
    void rebuildDirectoryList();

    MonitorController *m_controller = nullptr;
    QCheckBox *m_masterCheck = nullptr;
    QList<QCheckBox *> m_sourceChecks;
    QLineEdit *m_dirEdit = nullptr;
    QListWidget *m_dirList = nullptr;
    QListWidget *m_logList = nullptr;
    QTabWidget *m_tabs = nullptr;
};

#endif // PIXIU_MONITOR_CENTER_DIALOG_H
```

- [ ] **Step 4: 实现 MonitorCenterDialog.cpp**

```cpp
#include "widgets/MonitorCenterDialog.h"

#include "app/MonitorController.h"
#include "app/UiTokens.h"

#include <QCheckBox>
#include <QDateTime>
#include <QFileDialog>
#include <QHBoxLayout>
#include <QLabel>
#include <QLineEdit>
#include <QListWidget>
#include <QPushButton>
#include <QTabWidget>
#include <QVBoxLayout>

namespace {
QString sourceLabel(MonitorSource source)
{
    switch (source) {
    case MonitorSource::Directory:
        return MonitorCenterDialog::tr("目录文件监视");
    case MonitorSource::Clipboard:
        return MonitorCenterDialog::tr("剪贴板捕获");
    case MonitorSource::Behavior:
        return MonitorCenterDialog::tr("应用使用行为");
    case MonitorSource::Screenshot:
        return MonitorCenterDialog::tr("截屏识别");
    }
    return QString();
}

QString sourceHint(MonitorSource source)
{
    switch (source) {
    case MonitorSource::Directory:
        return MonitorCenterDialog::tr("监视下方目录，新文件自动识别入库");
    case MonitorSource::Clipboard:
        return MonitorCenterDialog::tr("复制较长文本或图片时自动捕获");
    case MonitorSource::Behavior:
        return MonitorCenterDialog::tr("记录常用应用与操作习惯，用于偏好提取");
    case MonitorSource::Screenshot:
        return MonitorCenterDialog::tr("截屏内容经 OCR 后沉淀为记忆");
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

    // 初始状态回填。
    m_masterCheck->setChecked(m_controller->isEnabled());
    for (int i = 0; i < m_sourceChecks.size(); ++i) {
        m_sourceChecks.at(i)->setChecked(
            m_controller->isSourceEnabled(static_cast<MonitorSource>(i)));
        m_sourceChecks.at(i)->setEnabled(m_controller->isEnabled());
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
```

注意：`sourceLabel` 使用了 `MonitorCenterDialog::tr` 但处于匿名 namespace——改为在匿名 namespace 中使用 `QCoreApplication::translate("MonitorCenterDialog", "...")`（与 `MemoryPanel.cpp:35` 既有做法一致），避免静态函数无法用成员 tr 的问题。

- [ ] **Step 5: 注册构建目标**

主执行列表追加 `src/widgets/MonitorCenterDialog.h` 与 `.cpp`；测试区块追加：

```cmake
    add_executable(t_monitor_center
        tests/t_monitor_center.cpp
        src/app/AppSettings.h
        src/app/AppSettings.cpp
        src/app/MonitorController.h
        src/app/MonitorController.cpp
        src/widgets/MonitorCenterDialog.h
        src/widgets/MonitorCenterDialog.cpp
    )
    target_include_directories(t_monitor_center PRIVATE ${CMAKE_CURRENT_SOURCE_DIR}/src)
    target_link_libraries(t_monitor_center PRIVATE Qt5::Test Qt5::Widgets)
    add_test(NAME monitor_center COMMAND t_monitor_center)
```

并把 `monitor_center` 加入 offscreen ENV 列表。

- [ ] **Step 6: 运行测试通过**

Run: `cmake --build build/frontend -j && QT_QPA_PLATFORM=offscreen ctest --test-dir build/frontend -R "monitor_" --output-on-failure`
Expected: 2/2 Passed

- [ ] **Step 7: Commit**

```bash
git add frontend/src/widgets/MonitorCenterDialog.h frontend/src/widgets/MonitorCenterDialog.cpp \
        frontend/tests/t_monitor_center.cpp frontend/CMakeLists.txt
git commit -m "feat(frontend): add monitor center dialog"
```

---

### Task 3: 入口接线（托盘/悬浮球暂停 + 设置入口 + 状态徽标）

**Covers:** 掌控层·全局暂停开关三入口 + 监控状态可感知（徽标）

**Files:**
- Modify: `frontend/src/app/TrayIcon.h/.cpp`
- Modify: `frontend/src/widgets/FloatingBall.h/.cpp`
- Modify: `frontend/src/services/NotifyService.h/.cpp`（无改动则不动）
- Modify: `frontend/src/widgets/InputBar.h/.cpp`
- Modify: `frontend/src/widgets/ChatWindow.h/.cpp`
- Modify: `frontend/src/widgets/SettingsDialog.h/.cpp`
- Modify: `frontend/src/app/PixiuApp.h/.cpp`
- Test: `frontend/tests/t_app_navigation.cpp`（追加用例）

**Interfaces:**
- Consumes: Task 1 `MonitorController`、Task 2 `MonitorCenterDialog`
- Produces:
  - `TrayIcon::pauseMonitorRequested()` 信号、`TrayIcon::setPauseActionText(const QString&)`
  - `FloatingBall::pauseMonitorRequested()` 信号、`FloatingBall::setPauseMenuText(const QString&)`
  - `FloatingBall::monitorCenterRequested()` 信号
  - `SettingsDialog::monitorCenterRequested()` 信号
  - `ChatWindow::setMonitorActive(bool)` → `InputBar::setMonitorActive(bool)`（徽标 `inputMonitorBadge`）
  - `PixiuApp` 私有槽 `openMonitorCenter()` 与成员 `m_monitorController/m_monitorCenter`

- [ ] **Step 1: 先写失败导航测试（追加到 t_app_navigation.cpp）**

在 `private slots:` 增加：

```cpp
    void pauseToggleFromBallFlipsController();
    void settingsOpensMonitorCenter();
```

实现（类成员区补 `MonitorController *m_monitor = nullptr;` 与访问器）：

```cpp
void TestAppNavigation::pauseToggleFromBallFlipsController()
{
    // 悬浮球菜单“暂停/继续监控”必须翻转控制器全局开关并刷新菜单文案。
    FloatingBall *ball = topLevels<FloatingBall>().first();
    QAction *pause =
        ball->findChild<QAction *>(QStringLiteral("pauseMonitorAction"));
    QVERIFY(pause != nullptr);

    MonitorController *controller =
        m_app->findChild<MonitorController *>();
    QVERIFY(controller != nullptr);
    const bool before = controller->isEnabled();
    pause->trigger();
    QCOMPARE(controller->isEnabled(), !before);
    QCOMPARE(pause->text(), !before ? QStringLiteral("暂停监控")
                                    : QStringLiteral("继续监控"));
    pause->trigger();
    QCOMPARE(controller->isEnabled(), before);
}

void TestAppNavigation::settingsOpensMonitorCenter()
{
    // 设置对话框中的“监控中心…”按钮打开监控中心面板。
    clickChip("settingsChip");
    SettingsDialog *settings = topLevels<SettingsDialog>().first();
    QPushButton *button = settings->findChild<QPushButton *>(
        QStringLiteral("openMonitorCenterButton"));
    QVERIFY(button != nullptr);
    QTest::mouseClick(button, Qt::LeftButton);
    QTRY_VERIFY(!topLevels<MonitorCenterDialog>().isEmpty());
    QTRY_VERIFY(topLevels<MonitorCenterDialog>().first()->isVisible());
}
```

同时在 `initTestCase()` 里 `qputenv("USER", ...)` 之后无需改动；顶部 include 补 `"app/MonitorController.h"` 与 `"widgets/MonitorCenterDialog.h"`、`"widgets/FloatingBall.h"`。

- [ ] **Step 2: 运行确认失败**

Run: `cmake --build build/frontend -j && QT_QPA_PLATFORM=offscreen ctest --test-dir build/frontend -R app_navigation --output-on-failure`
Expected: FAIL（找不到 `pauseMonitorAction`）

- [ ] **Step 3: TrayIcon/FloatingBall 增加暂停入口**

`TrayIcon.h` signals 区追加：

```cpp
    // 用户点击“暂停/继续监控”。
    void pauseMonitorRequested();
```

public 区追加：

```cpp
    // 更新暂停动作文案（paused=true 显示“继续监控”）。
    void setPauseActionText(const QString &text);
```

私有成员 `QAction *m_pauseAction = nullptr;`。`buildMenu()` 中在“退出”前插入：

```cpp
    m_pauseAction = menu->addAction(tr("暂停监控"));
    m_pauseAction->setObjectName(QStringLiteral("pauseMonitorAction"));
    connect(m_pauseAction, &QAction::triggered,
            this, &TrayIcon::pauseMonitorRequested);
```

`setPauseActionText` 实现为 `if (m_pauseAction) m_pauseAction->setText(text);`

`FloatingBall.h` signals 追加 `void pauseMonitorRequested(); void monitorCenterRequested();`，public 追加 `void setPauseMenuText(const QString &text);`，私有成员 `QAction *m_pauseAction = nullptr;`。`buildContextMenu()` 中在 separator 前插入：

```cpp
    QAction *centerAction = m_contextMenu->addAction(tr("监控中心"));
    centerAction->setObjectName(QStringLiteral("monitorCenterAction"));
    connect(centerAction, &QAction::triggered,
            this, &FloatingBall::monitorCenterRequested);

    m_pauseAction = m_contextMenu->addAction(tr("暂停监控"));
    m_pauseAction->setObjectName(QStringLiteral("pauseMonitorAction"));
    connect(m_pauseAction, &QAction::triggered,
            this, &FloatingBall::pauseMonitorRequested);
```

`setPauseMenuText` 同理设置文本。

- [ ] **Step 4: InputBar 监控徽标 + ChatWindow 转发**

`InputBar.h` public 追加 `void setMonitorActive(bool active);`，成员追加 `QLabel *m_monitorBadge = nullptr;`。构造函数中 `m_stateBadge` 创建之后：

```cpp
    m_monitorBadge = new QLabel(card);
    m_monitorBadge->setObjectName(QStringLiteral("inputMonitorBadge"));
    m_monitorBadge->setAccessibleName(tr("监控状态"));
    m_monitorBadge->hide();
```

`bottomRow` 组装处 `bottomRow->addWidget(m_stateBadge);` 之后插入 `bottomRow->addWidget(m_monitorBadge);`。实现：

```cpp
void InputBar::setMonitorActive(bool active)
{
    // active=false 时显示“⏸ 已暂停”；active=true 徽标隐藏（默认在线观感）。
    if (!m_monitorBadge) {
        return;
    }
    m_monitorBadge->setText(tr("⏸ 已暂停"));
    m_monitorBadge->setStyleSheet(ui::textStyle(ui::Role::Warning));
    m_monitorBadge->setVisible(!active);
}
```

`ChatWindow.h` public 追加 `void setMonitorActive(bool active);`，实现转发 `m_inputBar->setMonitorActive(active);`

- [ ] **Step 5: SettingsDialog 增加监控中心入口**

`SettingsDialog.h` signals 追加 `void monitorCenterRequested();`，成员追加 `QPushButton *m_monitorButton = nullptr;`。构造函数 shortcutHint 之后创建：

```cpp
    m_monitorButton = new QPushButton(tr("监控中心…"), this);
    m_monitorButton->setObjectName(QStringLiteral("openMonitorCenterButton"));
    m_monitorButton->setAccessibleName(tr("打开监控中心"));
    m_monitorButton->setCursor(Qt::PointingHandCursor);
    connect(m_monitorButton, &QPushButton::clicked,
            this, &SettingsDialog::monitorCenterRequested);
```

layout 中 `layout->addLayout(formLayout);` 之后插入 `layout->addWidget(m_monitorButton);`

- [ ] **Step 6: PixiuApp 统一接线**

`PixiuApp.h` 前置声明追加 `class MonitorController; class MonitorCenterDialog;`；成员追加：

```cpp
    MonitorController *m_monitorController = nullptr;
    MonitorCenterDialog *m_monitorCenter = nullptr;
```

私有方法声明追加 `void openMonitorCenter(); void refreshMonitorUi();`

`PixiuApp.cpp` include 追加两对新头文件。`start()` 中 `m_settings` 创建之后插入：

```cpp
    // 监控掌控层：状态单一事实来源 + 三入口（托盘/悬浮球/设置）。
    m_monitorController = new MonitorController(m_settings, this);
    connect(m_monitorController, &MonitorController::enabledChanged,
            this, [this](bool on) {
                m_chatWindow->setMonitorActive(on);
                const QString pauseText =
                    on ? tr("暂停监控") : tr("继续监控");
                if (m_tray) {
                    m_tray->setPauseActionText(pauseText);
                }
                if (m_floatingBall) {
                    m_floatingBall->setPauseMenuText(pauseText);
                }
            });
    connect(m_tray, &TrayIcon::pauseMonitorRequested, this, [this]() {
        m_monitorController->setEnabled(!m_monitorController->isEnabled());
    });
    connect(m_floatingBall, &FloatingBall::pauseMonitorRequested, this, [this]() {
        m_monitorController->setEnabled(!m_monitorController->isEnabled());
    });
    connect(m_floatingBall, &FloatingBall::monitorCenterRequested,
            this, &PixiuApp::openMonitorCenter);
    connect(m_chatWindow, &ChatWindow::settingsRequested,
            this, &PixiuApp::openSettings);
    // 初始徽标按已存偏好回填。
    m_chatWindow->setMonitorActive(m_monitorController->isEnabled());
```

注意：该代码块必须放在聊天窗与悬浮球均已创建之后（建议置于“各入口统一唤起聊天框”connect 区块之后）。`openSettings()` 内 `accepted` 连接之外追加一次性入口接线：

```cpp
        connect(m_settingsDialog, &SettingsDialog::monitorCenterRequested,
                this, &PixiuApp::openMonitorCenter);
```

新增方法实现：

```cpp
void PixiuApp::openMonitorCenter()
{
    if (!m_monitorCenter) {
        m_monitorCenter = new MonitorCenterDialog(m_monitorController);
    }
    m_monitorCenter->showAndFocus();
}
```

- [ ] **Step 7: 注册 t_app_navigation 新源文件**

`t_app_navigation` 目标的源文件列表追加 `src/app/MonitorController.h/.cpp`、`src/widgets/MonitorCenterDialog.h/.cpp`。

- [ ] **Step 8: 运行导航测试与全量回归**

Run: `cmake --build build/frontend -j && QT_QPA_PLATFORM=offscreen ctest --test-dir build/frontend --output-on-failure`
Expected: 全部 Passed（31 + 新增 ≥ 34）

- [ ] **Step 9: Commit**

```bash
git add frontend/src/app/TrayIcon.h frontend/src/app/TrayIcon.cpp \
        frontend/src/widgets/FloatingBall.h frontend/src/widgets/FloatingBall.cpp \
        frontend/src/widgets/InputBar.h frontend/src/widgets/InputBar.cpp \
        frontend/src/widgets/ChatWindow.h frontend/src/widgets/ChatWindow.cpp \
        frontend/src/widgets/SettingsDialog.h frontend/src/widgets/SettingsDialog.cpp \
        frontend/src/app/PixiuApp.h frontend/src/app/PixiuApp.cpp \
        frontend/tests/t_app_navigation.cpp frontend/CMakeLists.txt
git commit -m "feat(frontend): wire monitor pause controls and center entry points"
```

---

### Task 4: 跨模块 API 契约需求单

**Covers:** 批次②前置条件——`/monitor/*` 契约先行定义（Module B/C 待实现）

**Files:**
- Create: `frontend/docs/MONITOR_API_REQUIREMENTS.md`

**Interfaces:**
- Produces: 批次②前端 transport 扩展所依赖的端点/事件形状定义

- [ ] **Step 1: 写契约需求文档**

```markdown
# 监控引擎 API 契约需求单（Module A → Module B/C）

> 来源：产品愿景「一次配置，永久监控」掌控层批次①落地后的批次②前置需求。
> 状态：⬜ 待 Module B/C 评审实现；本文档为前端消费方的期望契约，
> 最终以 docs/API.md 双方确认为准。

## 1. 配置读写

### GET /monitor/config
响应 200：
{"enabled": false,
 "sources": {"directory": false, "clipboard": false,
             "behavior": false, "screenshot": false},
 "directories": ["/home/u/Downloads"]}

### PUT /monitor/config
请求体同上；服务端持久化并对 daemon 热生效。
错误：400 INVALID_REQUEST（未知 source 名等）。

## 2. 活动日志

### GET /monitor/log?limit=100&offset=0
响应 200：
{"events": [{"ts": 1756080000,
             "source": "directory|clipboard|behavior|screenshot|system",
             "status": "ingested|sensitive_quarantined|ignored|state_changed",
             "summary": "记住文件 支出清单.xlsx",
             "evidence_id": "evd_...", "knowledge_id": "knw_..."}]}
summary 由服务端生成用户可读文案（不得含敏感原文全文）。

## 3. WS 实时事件（/events 新增业务事件类型）

capture_event：
{"event":"capture_event","data":{"source":"directory",
 "status":"ingested","summary":"记住文件 支出清单.xlsx",
 "ts":1756080000,"evidence_id":"evd_..."}}

前端行为映射：角标+1（可选）、活动记录实时追加；
sensitive_quarantined 额外弹通知（批次③隔离区交互）。

## 4. 行为边界

- daemon 关停时配置仍持久；前端离线时展示本地缓存的上次配置。
- 敏感度判定沿用写入链路 detector；quarantined 条目不入 shared:*。
```

- [ ] **Step 2: Commit**

```bash
git add frontend/docs/MONITOR_API_REQUIREMENTS.md
git commit -m "docs(frontend): draft monitor api contract requirements"
```

---

### Task 5: i18n 收尾与全量验证

**Files:**
- Modify: `frontend/resources/i18n/pixiu_en_US.ts`（lupdate 自动生成）
- Regenerate: `frontend/resources/i18n/pixiu_en_US.qm`

- [ ] **Step 1: 更新翻译资源**

Run: `cd frontend/resources && lupdate ../src ../tests -ts pixiu_en_US.ts && lrelease pixiu_en_US.ts`
Expected: `.ts` 新增监控相关条目；`lrelease` 输出 0 unfinished（若出现未完成条目，逐条补英文翻译后再跑 lrelease）

- [ ] **Step 2: 全量双路径回归**

Run: `bash frontend/scripts/regression.sh`
Expected: `regression passed`（OFF/ON 构建、ctest 全绿、desktop 校验、deb 校验）

- [ ] **Step 3: Commit**

```bash
git add frontend/resources/i18n/
git commit -m "chore(frontend): regenerate i18n resources for monitor center"
```

---

## Self-Review 结论

- **覆盖核对**：掌控层 19 项脑暴中的第 1（监控中心）、第 2（全局暂停三入口）、第 3（活动日志 MVP 视图）均映射到 Task 1–3；第 4（引导向导）与捕获/递送层明确划入批次②③④，不在本计划冒进。契约需求单（Task 4）锁定批次②边界。
- **占位扫描**：无 TBD/TODO；所有代码步骤给出完整实现。
- **类型一致性**：`MonitorSource`/`MonitorLogEntry`/`MonitorController` 方法签名在 Task 2/3 引用处与 Task 1 定义一致；`setPauseActionText`/`setPauseMenuText` 名称在 Tray 与 Ball 两处保持区分（有意不同命名，避免混淆）。
