#include <QCheckBox>
#include <QDialog>
#include <QJsonArray>
#include <QJsonObject>
#include <QLabel>
#include <QLayout>
#include <QLineEdit>
#include <QListWidget>
#include <QPushButton>
#include <QSignalSpy>
#include <QTabWidget>
#include <QTest>

#include "app/UiTokens.h"
#include "widgets/MemoryPanel.h"
#include "widgets/PairDialog.h"

// MemoryPanel 壳测试：三个 Tab 及标题。
class TestMemoryPanel : public QObject
{
    Q_OBJECT

private slots:
    void hasThreeTabs();
    void tabTitlesMatchPlan();
    void setConflictsPopulatesList();
    void setConflictsMarksSeverityByColor();
    void setConflictsShowsEmptyState();
    void setConflictsLoadingShowsLoadingState();
    void setConflictsErrorShowsErrorAndRetry();
    void setConflictsSuccessHidesErrorState();
    void loadButtonEmitsHistoryRequested();
    void setPreferenceHistoryPopulatesList();
    void setPreferenceHistoryLoadingShowsLoadingState();
    void setPreferenceHistoryErrorShowsErrorAndRetry();
    void setPreferenceHistorySuccessHidesErrorState();
    void prefInputHasAccessibleName();
    void panelMarginsUseSpacingToken();
    void syncTabHasPairButtonOpensDialog();
    void showConflictTabSelectsTab();
    void showSyncTabSelectsTab();
    void setSyncStatusUpdatesLabel();
    void syncTabRefreshButtonEmitsRequest();
    void setPeersPopulatesList();
    void setPeersShowsEmptyState();
    void longPeerNameIsElided();
    void setSyncSummaryUpdatesLabel();
    void syncMasterSwitchDefaultOn();
    void syncMasterToggleEmitsSettingsRequest();
    void syncPauseToggleEmitsSettingsRequest();
    void setSyncSettingsGatesChildControls();
    void discoverListRendersAndPairButtonEmits();
    void discoverListShowsEmptyState();
    void syncNowButtonEmitsRequest();
    void conflictBannerCountsAndJumps();
    void leaveNetworkFlowShowsConfirmAndEmits();
    void extractButtonEmitsRequest();
    void extractFeedbackShowsResultAndError();
    void escHidesPanel();
};

void TestMemoryPanel::hasThreeTabs()
{
    MemoryPanel panel;
    QTabWidget *tabs = panel.findChild<QTabWidget *>();
    QVERIFY(tabs != nullptr);
    QCOMPARE(tabs->count(), 3);
}

void TestMemoryPanel::tabTitlesMatchPlan()
{
    MemoryPanel panel;
    QTabWidget *tabs = panel.findChild<QTabWidget *>();
    QCOMPARE(tabs->tabText(0), QStringLiteral("偏好"));
    QCOMPARE(tabs->tabText(1), QStringLiteral("冲突"));
    QCOMPARE(tabs->tabText(2), QStringLiteral("同步"));
}

void TestMemoryPanel::setConflictsPopulatesList()
{
    MemoryPanel panel;
    QJsonArray conflicts;
    conflicts.append(QJsonObject{
        {QStringLiteral("knowledge_title"), QStringLiteral("2026年4月家庭支出清单")},
        {QStringLiteral("field"), QStringLiteral("body.items[2].amount")},
        {QStringLiteral("old_value"), 156},
        {QStringLiteral("new_value"), 186},
        {QStringLiteral("resolution"), QStringLiteral("NEW_WINS")},
        {QStringLiteral("created_at"), 1714608000}});
    conflicts.append(QJsonObject{
        {QStringLiteral("knowledge_title"), QStringLiteral("燃气费修正")},
        {QStringLiteral("resolution"), QStringLiteral("NEW_WINS")}});

    panel.setConflicts(conflicts);

    QListWidget *list = panel.findChild<QListWidget *>(QStringLiteral("conflictList"));
    QVERIFY(list != nullptr);
    QCOMPARE(list->count(), 2);
    QVERIFY(list->item(0)->text().contains(
        QStringLiteral("2026年4月家庭支出清单")));
    QVERIFY(list->item(0)->text().contains(QStringLiteral("156 → 186")));
    QVERIFY(!list->isHidden());
}

void TestMemoryPanel::setConflictsMarksSeverityByColor()
{
    // F3-1：冲突条目按 severity 标记（low 灰 / medium 蓝 / high 红）；
    // 缺省/未知 severity 按 high 着色（与打扰分流缺省一致）。
    MemoryPanel panel;
    QJsonArray conflicts;
    conflicts.append(QJsonObject{
        {QStringLiteral("knowledge_title"), QStringLiteral("支出清单")},
        {QStringLiteral("resolution"), QStringLiteral("MERGE")},
        {QStringLiteral("severity"), QStringLiteral("low")}});
    conflicts.append(QJsonObject{
        {QStringLiteral("knowledge_title"), QStringLiteral("支出清单")},
        {QStringLiteral("resolution"), QStringLiteral("NEW_WINS")},
        {QStringLiteral("severity"), QStringLiteral("medium")}});
    conflicts.append(QJsonObject{
        {QStringLiteral("knowledge_title"), QStringLiteral("支出清单")},
        {QStringLiteral("resolution"), QStringLiteral("MANUAL")},
        {QStringLiteral("severity"), QStringLiteral("high")}});
    conflicts.append(QJsonObject{
        {QStringLiteral("knowledge_title"), QStringLiteral("支出清单")},
        {QStringLiteral("resolution"), QStringLiteral("MANUAL")}});

    panel.setConflicts(conflicts);

    QListWidget *list =
        panel.findChild<QListWidget *>(QStringLiteral("conflictList"));
    QVERIFY(list != nullptr);
    QCOMPARE(list->count(), 4);
    QCOMPARE(list->item(0)->foreground().color(),
             ui::semanticColor(ui::Role::Muted));
    QCOMPARE(list->item(1)->foreground().color(),
             ui::semanticColor(ui::Role::Accent));
    QCOMPARE(list->item(2)->foreground().color(),
             ui::semanticColor(ui::Role::Error));
    QCOMPARE(list->item(3)->foreground().color(),
             ui::semanticColor(ui::Role::Error));
    // severity 标记不破坏既有分辨率文本。
    QVERIFY(list->item(2)->text().contains(QStringLiteral("裁决：MANUAL")));
    QVERIFY(list->item(1)->text().contains(QStringLiteral("裁决：NEW_WINS")));
}

void TestMemoryPanel::setConflictsShowsEmptyState()
{
    MemoryPanel panel;
    panel.setConflicts(QJsonArray());

    QListWidget *list = panel.findChild<QListWidget *>(QStringLiteral("conflictList"));
    QVERIFY(list != nullptr);
    QCOMPARE(list->count(), 0);
    QVERIFY(list->isHidden());
}

void TestMemoryPanel::setConflictsLoadingShowsLoadingState()
{
    MemoryPanel panel;
    panel.setConflictsLoading();

    QLabel *emptyLabel =
        panel.findChild<QLabel *>(QStringLiteral("conflictEmptyLabel"));
    QListWidget *list =
        panel.findChild<QListWidget *>(QStringLiteral("conflictList"));
    QLabel *errorLabel =
        panel.findChild<QLabel *>(QStringLiteral("conflictErrorLabel"));
    QVERIFY(emptyLabel != nullptr);
    QVERIFY(list != nullptr);
    QVERIFY(errorLabel != nullptr);

    QCOMPARE(emptyLabel->text(), QStringLiteral("正在加载…"));
    QVERIFY(!emptyLabel->isHidden());
    QVERIFY(list->isHidden());
    QVERIFY(errorLabel->isHidden());

    // 成功加载后恢复空态文案，不再残留“正在加载”。
    panel.setConflicts(QJsonArray());
    QCOMPARE(emptyLabel->text(), QStringLiteral("暂无冲突记录"));
    QVERIFY(!emptyLabel->isHidden());
}

void TestMemoryPanel::setConflictsErrorShowsErrorAndRetry()
{
    MemoryPanel panel;
    panel.setConflictsError(QStringLiteral("后端不可达"));

    QLabel *errorLabel =
        panel.findChild<QLabel *>(QStringLiteral("conflictErrorLabel"));
    QPushButton *retryButton =
        panel.findChild<QPushButton *>(QStringLiteral("conflictRetryButton"));
    QListWidget *list =
        panel.findChild<QListWidget *>(QStringLiteral("conflictList"));
    QLabel *emptyLabel =
        panel.findChild<QLabel *>(QStringLiteral("conflictEmptyLabel"));
    QVERIFY(errorLabel != nullptr);
    QVERIFY(retryButton != nullptr);
    QVERIFY(list != nullptr);
    QVERIFY(emptyLabel != nullptr);

    QCOMPARE(errorLabel->text(), QStringLiteral("后端不可达"));
    QVERIFY(!errorLabel->isHidden());
    QVERIFY(!retryButton->isHidden());
    // 失败态与空态互斥：错误展示时不得显示“暂无冲突记录”。
    QVERIFY(list->isHidden());
    QVERIFY(emptyLabel->isHidden());

    QSignalSpy retrySpy(&panel, &MemoryPanel::conflictRetryRequested);
    QTest::mouseClick(retryButton, Qt::LeftButton);
    QCOMPARE(retrySpy.count(), 1);
}

void TestMemoryPanel::setConflictsSuccessHidesErrorState()
{
    MemoryPanel panel;
    panel.setConflictsError(QStringLiteral("后端不可达"));
    panel.setConflicts(QJsonArray{
        QJsonObject{{QStringLiteral("knowledge_title"),
                     QStringLiteral("2026年4月家庭支出清单")}}});

    QLabel *errorLabel =
        panel.findChild<QLabel *>(QStringLiteral("conflictErrorLabel"));
    QPushButton *retryButton =
        panel.findChild<QPushButton *>(QStringLiteral("conflictRetryButton"));
    QVERIFY(errorLabel != nullptr);
    QVERIFY(retryButton != nullptr);
    QVERIFY(errorLabel->isHidden());
    QVERIFY(retryButton->isHidden());
}

void TestMemoryPanel::loadButtonEmitsHistoryRequested()
{
    MemoryPanel panel;
    QSignalSpy spy(&panel, &MemoryPanel::historyRequested);

    QLineEdit *input = panel.findChild<QLineEdit *>();
    QVERIFY(input != nullptr);
    input->setText(QStringLiteral("pref_abc"));

    QPushButton *button = nullptr;
    const QList<QPushButton *> buttons = panel.findChildren<QPushButton *>();
    for (QPushButton *candidate : buttons) {
        if (candidate->text() == QStringLiteral("加载历史")) {
            button = candidate;
            break;
        }
    }
    QVERIFY(button != nullptr);
    QTest::mouseClick(button, Qt::LeftButton);
    QCOMPARE(spy.count(), 1);
    QCOMPARE(spy.takeFirst().at(0).toString(), QStringLiteral("pref_abc"));
}

void TestMemoryPanel::setPreferenceHistoryPopulatesList()
{
    MemoryPanel panel;
    QJsonObject response;
    response.insert(QStringLiteral("id"), QStringLiteral("pref_abc"));
    response.insert(QStringLiteral("key"), QStringLiteral("output_style.compact"));
    response.insert(QStringLiteral("current_version"), 3);
    response.insert(QStringLiteral("history"), QJsonArray{
        QJsonObject{
            {QStringLiteral("version"), 1},
            {QStringLiteral("updated_at"), 1714435200},
            {QStringLiteral("value"), QJsonObject{{QStringLiteral("enabled"), false}}}},
        QJsonObject{
            {QStringLiteral("version"), 2},
            {QStringLiteral("updated_at"), 1714521600},
            {QStringLiteral("value"), QJsonObject{{QStringLiteral("enabled"), true}}}}});

    panel.setPreferenceHistory(response);

    QListWidget *list =
        panel.findChild<QListWidget *>(QStringLiteral("prefHistoryList"));
    QVERIFY(list != nullptr);
    QCOMPARE(list->count(), 2);
    QVERIFY(list->item(0)->text().contains(QStringLiteral("v1")));
    QVERIFY(list->item(0)->text().contains(QStringLiteral("\"enabled\":false")));
    QVERIFY(!list->isHidden());
}

void TestMemoryPanel::setPreferenceHistoryLoadingShowsLoadingState()
{
    MemoryPanel panel;
    panel.setPreferenceHistoryLoading();

    QLabel *emptyLabel =
        panel.findChild<QLabel *>(QStringLiteral("prefEmptyLabel"));
    QListWidget *list =
        panel.findChild<QListWidget *>(QStringLiteral("prefHistoryList"));
    QLabel *errorLabel =
        panel.findChild<QLabel *>(QStringLiteral("prefErrorLabel"));
    QVERIFY(emptyLabel != nullptr);
    QVERIFY(list != nullptr);
    QVERIFY(errorLabel != nullptr);

    QCOMPARE(emptyLabel->text(), QStringLiteral("正在加载…"));
    QVERIFY(!emptyLabel->isHidden());
    QVERIFY(list->isHidden());
    QVERIFY(errorLabel->isHidden());

    // 成功加载后恢复空态文案。
    panel.setPreferenceHistory(QJsonObject{
        {QStringLiteral("key"), QStringLiteral("output_style.compact")},
        {QStringLiteral("current_version"), 0},
        {QStringLiteral("history"), QJsonArray()}});
    QCOMPARE(emptyLabel->text(), QStringLiteral("暂无历史记录"));
    QVERIFY(!emptyLabel->isHidden());
}

void TestMemoryPanel::setPreferenceHistoryErrorShowsErrorAndRetry()
{
    MemoryPanel panel;
    panel.setPreferenceHistoryError(QStringLiteral("服务异常"));

    QLabel *errorLabel =
        panel.findChild<QLabel *>(QStringLiteral("prefErrorLabel"));
    QPushButton *retryButton =
        panel.findChild<QPushButton *>(QStringLiteral("prefRetryButton"));
    QListWidget *list =
        panel.findChild<QListWidget *>(QStringLiteral("prefHistoryList"));
    QLabel *emptyLabel =
        panel.findChild<QLabel *>(QStringLiteral("prefEmptyLabel"));
    QVERIFY(errorLabel != nullptr);
    QVERIFY(retryButton != nullptr);
    QVERIFY(list != nullptr);
    QVERIFY(emptyLabel != nullptr);

    QCOMPARE(errorLabel->text(), QStringLiteral("服务异常"));
    QVERIFY(!errorLabel->isHidden());
    QVERIFY(!retryButton->isHidden());
    QVERIFY(list->isHidden());
    QVERIFY(emptyLabel->isHidden());

    QSignalSpy retrySpy(&panel, &MemoryPanel::preferenceRetryRequested);
    QTest::mouseClick(retryButton, Qt::LeftButton);
    QCOMPARE(retrySpy.count(), 1);
}

void TestMemoryPanel::setPreferenceHistorySuccessHidesErrorState()
{
    MemoryPanel panel;
    panel.setPreferenceHistoryError(QStringLiteral("服务异常"));
    panel.setPreferenceHistory(QJsonObject{
        {QStringLiteral("key"), QStringLiteral("output_style.compact")},
        {QStringLiteral("current_version"), 3},
        {QStringLiteral("history"), QJsonArray{
            QJsonObject{
                {QStringLiteral("version"), 1},
                {QStringLiteral("updated_at"), 1714435200},
                {QStringLiteral("value"),
                 QJsonObject{{QStringLiteral("enabled"), false}}}}}}});

    QLabel *errorLabel =
        panel.findChild<QLabel *>(QStringLiteral("prefErrorLabel"));
    QPushButton *retryButton =
        panel.findChild<QPushButton *>(QStringLiteral("prefRetryButton"));
    QVERIFY(errorLabel != nullptr);
    QVERIFY(retryButton != nullptr);
    QVERIFY(errorLabel->isHidden());
    QVERIFY(retryButton->isHidden());
}

void TestMemoryPanel::prefInputHasAccessibleName()
{
    MemoryPanel panel;
    QLineEdit *input = panel.findChild<QLineEdit *>();
    QVERIFY(input != nullptr);
    QVERIFY(!input->accessibleName().isEmpty());
}

void TestMemoryPanel::panelMarginsUseSpacingToken()
{
    MemoryPanel panel;
    QLayout *layout = panel.layout();
    QVERIFY(layout != nullptr);
    const QMargins margins = layout->contentsMargins();
    // 2026-08-10 侧边浮窗视觉统一：面板留白由 8px 提升到 12px（Spacing::M）。
    QCOMPARE(margins.left(), 12);
    QCOMPARE(margins.top(), 12);
    QCOMPARE(margins.right(), 12);
    QCOMPARE(margins.bottom(), 12);
}

void TestMemoryPanel::syncTabHasPairButtonOpensDialog()
{
    MemoryPanel panel;
    QPushButton *pairButton =
        panel.findChild<QPushButton *>(QStringLiteral("pairDeviceButton"));
    QVERIFY(pairButton != nullptr);

    // PairDialog 在首次点击时懒创建；先点击再查找并验证可见。
    panel.show();
    QTest::mouseClick(pairButton, Qt::LeftButton);
    PairDialog *dialog = panel.findChild<PairDialog *>();
    QVERIFY(dialog != nullptr);
    QVERIFY(dialog->isVisible());
}

void TestMemoryPanel::showConflictTabSelectsTab()
{
    MemoryPanel panel;
    QTabWidget *tabs = panel.findChild<QTabWidget *>();
    QVERIFY(tabs != nullptr);
    QCOMPARE(tabs->currentIndex(), 0);

    panel.showConflictTab();
    QCOMPARE(tabs->currentIndex(), 1);
}

void TestMemoryPanel::showSyncTabSelectsTab()
{
    MemoryPanel panel;
    QTabWidget *tabs = panel.findChild<QTabWidget *>();
    QVERIFY(tabs != nullptr);
    QCOMPARE(tabs->currentIndex(), 0);

    panel.showSyncTab();
    QCOMPARE(tabs->currentIndex(), 2);
}

void TestMemoryPanel::setSyncStatusUpdatesLabel()
{
    MemoryPanel panel;
    QLabel *status =
        panel.findChild<QLabel *>(QStringLiteral("syncStatusLabel"));
    QVERIFY(status != nullptr);

    panel.setSyncStatus(QStringLiteral("配对成功：客厅一体机"), true);
    QCOMPARE(status->text(), QStringLiteral("配对成功：客厅一体机"));
    QVERIFY(!status->isHidden());
}

void TestMemoryPanel::syncTabRefreshButtonEmitsRequest()
{
    MemoryPanel panel;
    QSignalSpy refreshSpy(&panel, &MemoryPanel::syncRefreshRequested);

    QPushButton *refreshButton =
        panel.findChild<QPushButton *>(QStringLiteral("syncRefreshButton"));
    QVERIFY(refreshButton != nullptr);
    QTest::mouseClick(refreshButton, Qt::LeftButton);
    QCOMPARE(refreshSpy.count(), 1);
}

void TestMemoryPanel::setPeersPopulatesList()
{
    MemoryPanel panel;
    QJsonArray peers;
    peers.append(QJsonObject{
        {QStringLiteral("id"), QStringLiteral("dev_self")},
        {QStringLiteral("name"), QStringLiteral("书房工作站")},
        {QStringLiteral("is_self"), true},
        {QStringLiteral("status"), QStringLiteral("ONLINE")}});
    peers.append(QJsonObject{
        {QStringLiteral("id"), QStringLiteral("dev_guest")},
        {QStringLiteral("name"), QStringLiteral("客厅一体机")},
        {QStringLiteral("is_self"), false},
        {QStringLiteral("status"), QStringLiteral("ONLINE")},
        {QStringLiteral("last_sync_ts"), 1714608000},
        {QStringLiteral("pending_ops"), 3}});

    panel.setPeers(peers);

    QListWidget *list =
        panel.findChild<QListWidget *>(QStringLiteral("peerList"));
    QVERIFY(list != nullptr);
    QCOMPARE(list->count(), 2);
    QWidget *row = list->itemWidget(list->item(0));
    QVERIFY(row != nullptr);
    bool hasSelfName = false;
    const QList<QLabel *> labels = row->findChildren<QLabel *>();
    for (QLabel *label : labels) {
        if (label->text().contains(QStringLiteral("书房工作站"))) {
            hasSelfName = true;
            break;
        }
    }
    QVERIFY(hasSelfName);
    QVERIFY(!list->isHidden());

    // SN-6：移除单设备解绑——节点行不再提供“解绑”按钮；整网退出改由
    // 「退出网络」按钮承载（存在非本机节点时可用）。
    QCOMPARE(panel.findChildren<QPushButton *>(QStringLiteral("revokeButton")).size(), 0);
    QPushButton *leaveButton =
        panel.findChild<QPushButton *>(QStringLiteral("leaveNetworkButton"));
    QVERIFY(leaveButton != nullptr);
    QVERIFY(leaveButton->isEnabled());

    QLabel *emptyLabel =
        panel.findChild<QLabel *>(QStringLiteral("syncEmptyLabel"));
    QVERIFY(emptyLabel != nullptr);
    QVERIFY(emptyLabel->isHidden());
}

void TestMemoryPanel::setPeersShowsEmptyState()
{
    MemoryPanel panel;
    panel.setPeers(QJsonArray());

    QListWidget *list =
        panel.findChild<QListWidget *>(QStringLiteral("peerList"));
    QVERIFY(list != nullptr);
    QCOMPARE(list->count(), 0);
    QVERIFY(list->isHidden());

    QLabel *emptyLabel =
        panel.findChild<QLabel *>(QStringLiteral("syncEmptyLabel"));
    QVERIFY(emptyLabel != nullptr);
    QVERIFY(!emptyLabel->isHidden());
}

void TestMemoryPanel::longPeerNameIsElided()
{
    MemoryPanel panel;
    const QString longName(120, QLatin1Char('A'));
    panel.setPeers(QJsonArray{
        QJsonObject{
            {QStringLiteral("id"), QStringLiteral("dev_long")},
            {QStringLiteral("name"), longName},
            {QStringLiteral("is_self"), false},
            {QStringLiteral("status"), QStringLiteral("OFFLINE")}}});

    QListWidget *list =
        panel.findChild<QListWidget *>(QStringLiteral("peerList"));
    QVERIFY(list != nullptr);
    QCOMPARE(list->count(), 1);

    QWidget *row = list->itemWidget(list->item(0));
    QVERIFY(row != nullptr);
    QLabel *nameLabel =
        row->findChild<QLabel *>(QStringLiteral("peerNameLabel"));
    QVERIFY(nameLabel != nullptr);
    // 长设备名行内省略，避免把在线状态挤出可视区。
    QVERIFY(nameLabel->text().size() < longName.size());
    QVERIFY(nameLabel->text().endsWith(QStringLiteral("…")));
}

void TestMemoryPanel::syncMasterSwitchDefaultOn()
{
    MemoryPanel panel;
    QCheckBox *master =
        panel.findChild<QCheckBox *>(QStringLiteral("syncMasterSwitch"));
    QVERIFY(master != nullptr);
    // 总开关默认开。
    QVERIFY(master->isChecked());
    QCheckBox *pause =
        panel.findChild<QCheckBox *>(QStringLiteral("syncPauseSwitch"));
    QVERIFY(pause != nullptr);
    QVERIFY(!pause->isChecked());
    QVERIFY(pause->isEnabled());
}

void TestMemoryPanel::syncMasterToggleEmitsSettingsRequest()
{
    MemoryPanel panel;
    QSignalSpy spy(&panel, &MemoryPanel::syncSettingsRequested);
    QCheckBox *master =
        panel.findChild<QCheckBox *>(QStringLiteral("syncMasterSwitch"));
    QVERIFY(master != nullptr);

    master->click();   // 关闭总开关
    QCOMPARE(spy.count(), 1);
    const QList<QVariant> args = spy.takeFirst();
    QCOMPARE(args.at(0).toBool(), false);   // enabled
    QCOMPARE(args.at(1).toBool(), false);   // paused 保持
}

void TestMemoryPanel::syncPauseToggleEmitsSettingsRequest()
{
    MemoryPanel panel;
    QSignalSpy spy(&panel, &MemoryPanel::syncSettingsRequested);
    QCheckBox *pause =
        panel.findChild<QCheckBox *>(QStringLiteral("syncPauseSwitch"));
    QVERIFY(pause != nullptr);

    pause->click();   // 暂停传输
    QCOMPARE(spy.count(), 1);
    const QList<QVariant> args = spy.takeFirst();
    QCOMPARE(args.at(0).toBool(), true);   // enabled 保持
    QCOMPARE(args.at(1).toBool(), true);   // paused
}

void TestMemoryPanel::setSyncSettingsGatesChildControls()
{
    MemoryPanel panel;
    QCheckBox *pause =
        panel.findChild<QCheckBox *>(QStringLiteral("syncPauseSwitch"));
    QPushButton *pair =
        panel.findChild<QPushButton *>(QStringLiteral("pairDeviceButton"));
    QPushButton *now =
        panel.findChild<QPushButton *>(QStringLiteral("syncNowButton"));
    QListWidget *discovered =
        panel.findChild<QListWidget *>(QStringLiteral("discoveredDeviceList"));
    QVERIFY(pause != nullptr);
    QVERIFY(pair != nullptr);
    QVERIFY(now != nullptr);
    QVERIFY(discovered != nullptr);
    QVERIFY(pause->isEnabled());
    QVERIFY(pair->isEnabled());
    QVERIFY(now->isEnabled());

    // 程序化回填（GET /sync/status 或 PUT 回声）不得发射请求信号（防回环）。
    QSignalSpy spy(&panel, &MemoryPanel::syncSettingsRequested);
    panel.setSyncSettings(false, true);
    QCOMPARE(spy.count(), 0);
    QVERIFY(!pause->isEnabled());
    QVERIFY(!pair->isEnabled());
    QVERIFY(!now->isEnabled());
    QVERIFY(!discovered->isEnabled());
    QVERIFY(pause->isChecked());   // paused=true 回填到开关

    // 重新开启后下级恢复可用。
    panel.setSyncSettings(true, false);
    QCOMPARE(spy.count(), 0);
    QVERIFY(pause->isEnabled());
    QVERIFY(pair->isEnabled());
    QVERIFY(now->isEnabled());
    QVERIFY(!pause->isChecked());
}

void TestMemoryPanel::discoverListRendersAndPairButtonEmits()
{
    MemoryPanel panel;
    QSignalSpy spy(&panel, &MemoryPanel::syncPairRequested);
    QJsonArray devices;
    devices.append(QJsonObject{
        {QStringLiteral("device_id"), QStringLiteral("dev_alpha")},
        {QStringLiteral("device_name"), QStringLiteral("Alpha 一体机")},
        {QStringLiteral("addresses"), QJsonArray{QStringLiteral("192.168.1.10")}},
        {QStringLiteral("pairable"), true},
        {QStringLiteral("paired"), false}});
    devices.append(QJsonObject{
        {QStringLiteral("device_id"), QStringLiteral("dev_beta")},
        {QStringLiteral("device_name"), QStringLiteral("Beta 笔记本")},
        {QStringLiteral("addresses"), QJsonArray{QStringLiteral("192.168.1.11")}},
        {QStringLiteral("pairable"), false},
        {QStringLiteral("paired"), false}});
    devices.append(QJsonObject{
        {QStringLiteral("device_id"), QStringLiteral("dev_gamma")},
        {QStringLiteral("device_name"), QStringLiteral("Gamma 平板")},
        {QStringLiteral("addresses"), QJsonArray{QStringLiteral("192.168.1.12")}},
        {QStringLiteral("pairable"), true},
        {QStringLiteral("paired"), true}});

    panel.setDiscoveredDevices(devices);

    QListWidget *list =
        panel.findChild<QListWidget *>(QStringLiteral("discoveredDeviceList"));
    QVERIFY(list != nullptr);
    QCOMPARE(list->count(), 3);
    QVERIFY(!list->isHidden());

    // 可配对且未配对设备有「配对」按钮；已配对 / 不可配对设备无按钮。
    QWidget *row0 = list->itemWidget(list->item(0));
    QVERIFY(row0 != nullptr);
    QLabel *nameLabel = row0->findChild<QLabel *>(QStringLiteral("discoverNameLabel"));
    QVERIFY(nameLabel != nullptr);
    QVERIFY(nameLabel->text().contains(QStringLiteral("Alpha 一体机")));
    QPushButton *pairButton =
        row0->findChild<QPushButton *>(QStringLiteral("discoverPairButton"));
    QVERIFY(pairButton != nullptr);

    QWidget *row1 = list->itemWidget(list->item(1));
    QVERIFY(row1->findChild<QPushButton *>(QStringLiteral("discoverPairButton"))
            == nullptr);
    QWidget *row2 = list->itemWidget(list->item(2));
    QVERIFY(row2->findChild<QPushButton *>(QStringLiteral("discoverPairButton"))
            == nullptr);

    QTest::mouseClick(pairButton, Qt::LeftButton);
    QCOMPARE(spy.count(), 1);
    QCOMPARE(spy.takeFirst().at(0).toString(), QStringLiteral("dev_alpha"));

    QLabel *empty =
        panel.findChild<QLabel *>(QStringLiteral("discoverEmptyLabel"));
    QVERIFY(empty != nullptr);
    QVERIFY(empty->isHidden());
}

void TestMemoryPanel::discoverListShowsEmptyState()
{
    MemoryPanel panel;
    panel.setDiscoveredDevices(QJsonArray());

    QListWidget *list =
        panel.findChild<QListWidget *>(QStringLiteral("discoveredDeviceList"));
    QLabel *empty =
        panel.findChild<QLabel *>(QStringLiteral("discoverEmptyLabel"));
    QVERIFY(list != nullptr);
    QVERIFY(empty != nullptr);
    QCOMPARE(list->count(), 0);
    QVERIFY(list->isHidden());
    QVERIFY(!empty->isHidden());
}

void TestMemoryPanel::syncNowButtonEmitsRequest()
{
    MemoryPanel panel;
    QSignalSpy spy(&panel, &MemoryPanel::syncNowRequested);
    QPushButton *button =
        panel.findChild<QPushButton *>(QStringLiteral("syncNowButton"));
    QVERIFY(button != nullptr);
    QTest::mouseClick(button, Qt::LeftButton);
    QCOMPARE(spy.count(), 1);
}

void TestMemoryPanel::conflictBannerCountsAndJumps()
{
    MemoryPanel panel;
    QPushButton *banner =
        panel.findChild<QPushButton *>(QStringLiteral("syncConflictBanner"));
    QVERIFY(banner != nullptr);
    // 初始计数 0：横幅隐藏。
    QVERIFY(banner->isHidden());

    panel.setSyncConflictCount(2);
    QVERIFY(!banner->isHidden());
    QVERIFY(banner->text().contains(QStringLiteral("2")));

    QTabWidget *tabs = panel.findChild<QTabWidget *>();
    QVERIFY(tabs != nullptr);
    QCOMPARE(tabs->currentIndex(), 0);
    QTest::mouseClick(banner, Qt::LeftButton);
    QCOMPARE(tabs->currentIndex(), 1);   // 点击跳转冲突 Tab

    panel.setSyncConflictCount(0);
    QVERIFY(banner->isHidden());
}

void TestMemoryPanel::leaveNetworkFlowShowsConfirmAndEmits()
{
    MemoryPanel panel;
    panel.setPeers(QJsonArray{
        QJsonObject{{QStringLiteral("id"), QStringLiteral("dev_self")},
                    {QStringLiteral("name"), QStringLiteral("书房工作站")},
                    {QStringLiteral("is_self"), true},
                    {QStringLiteral("status"), QStringLiteral("ONLINE")}},
        QJsonObject{{QStringLiteral("id"), QStringLiteral("dev_guest1")},
                    {QStringLiteral("name"), QStringLiteral("客厅一体机")},
                    {QStringLiteral("is_self"), false},
                    {QStringLiteral("status"), QStringLiteral("ONLINE")}},
        QJsonObject{{QStringLiteral("id"), QStringLiteral("dev_guest2")},
                    {QStringLiteral("name"), QStringLiteral("卧室平板")},
                    {QStringLiteral("is_self"), false},
                    {QStringLiteral("status"), QStringLiteral("OFFLINE")}}});

    QPushButton *leave =
        panel.findChild<QPushButton *>(QStringLiteral("leaveNetworkButton"));
    QVERIFY(leave != nullptr);
    // 存在 2 台非本机设备：退出入口可用。
    QVERIFY(leave->isEnabled());

    QSignalSpy leaveSpy(&panel, &MemoryPanel::syncLeaveRequested);
    QTest::mouseClick(leave, Qt::LeftButton);

    QDialog *dialog =
        panel.findChild<QDialog *>(QStringLiteral("leaveConfirmDialog"));
    QVERIFY(dialog != nullptr);
    QVERIFY(dialog->isVisible());
    QLabel *text = dialog->findChild<QLabel *>(QStringLiteral("leaveConfirmText"));
    QVERIFY(text != nullptr);
    QVERIFY(text->text().contains(QStringLiteral("2")));

    QPushButton *confirm =
        dialog->findChild<QPushButton *>(QStringLiteral("leaveConfirmButton"));
    QVERIFY(confirm != nullptr);
    QTest::mouseClick(confirm, Qt::LeftButton);
    QCOMPARE(leaveSpy.count(), 1);
}

void TestMemoryPanel::setSyncSummaryUpdatesLabel()
{
    MemoryPanel panel;
    panel.setSyncSummary(QJsonObject{
        {QStringLiteral("domain"), QStringLiteral("shared:home")},
        {QStringLiteral("peers_online"), 2},
        {QStringLiteral("peers_total"), 3},
        {QStringLiteral("pending_outgoing_ops"), 0},
        {QStringLiteral("last_anti_entropy_ts"), 1714608000},
        {QStringLiteral("total_ops_synced"), 1285}});

    QLabel *summary =
        panel.findChild<QLabel *>(QStringLiteral("syncSummaryLabel"));
    QVERIFY(summary != nullptr);
    QVERIFY(summary->text().contains(QStringLiteral("shared:home")));
    QVERIFY(summary->text().contains(QStringLiteral("在线 2/3")));
    QVERIFY(!summary->isHidden());
}

void TestMemoryPanel::extractButtonEmitsRequest()
{
    MemoryPanel panel;
    QPushButton *button =
        panel.findChild<QPushButton *>(QStringLiteral("prefExtractButton"));
    QVERIFY(button != nullptr);
    QSignalSpy spy(&panel, &MemoryPanel::extractPreferencesRequested);

    QTest::mouseClick(button, Qt::LeftButton);

    QCOMPARE(spy.count(), 1);
}

void TestMemoryPanel::extractFeedbackShowsResultAndError()
{
    MemoryPanel panel;
    QLabel *label =
        panel.findChild<QLabel *>(QStringLiteral("prefExtractLabel"));
    QVERIFY(label != nullptr);

    panel.setPreferenceExtractResult(2);
    QVERIFY(!label->isHidden());
    QVERIFY(label->text().contains(QStringLiteral("2")));

    panel.setPreferenceExtractError(QStringLiteral("提取失败"));
    QVERIFY(!label->isHidden());
    QCOMPARE(label->text(), QStringLiteral("提取失败"));
}

void TestMemoryPanel::escHidesPanel()
{
    MemoryPanel panel;
    panel.show();
    QVERIFY(panel.isVisible());

    QTest::keyClick(&panel, Qt::Key_Escape);
    QVERIFY(!panel.isVisible());
}

QTEST_MAIN(TestMemoryPanel)
#include "t_memory_panel.moc"
