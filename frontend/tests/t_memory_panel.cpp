#include <QJsonArray>
#include <QJsonObject>
#include <QLabel>
#include <QLineEdit>
#include <QListWidget>
#include <QPushButton>
#include <QSignalSpy>
#include <QTabWidget>
#include <QTest>

#include "widgets/MemoryPanel.h"
#include "widgets/PairDialog.h"
#include "widgets/RevokeDialog.h"

// MemoryPanel 壳测试：三个 Tab 及标题。
class TestMemoryPanel : public QObject
{
    Q_OBJECT

private slots:
    void hasThreeTabs();
    void tabTitlesMatchPlan();
    void setConflictsPopulatesList();
    void setConflictsShowsEmptyState();
    void setConflictsLoadingShowsLoadingState();
    void setConflictsErrorShowsErrorAndRetry();
    void setConflictsSuccessHidesErrorState();
    void loadButtonEmitsHistoryRequested();
    void setPreferenceHistoryPopulatesList();
    void setPreferenceHistoryLoadingShowsLoadingState();
    void setPreferenceHistoryErrorShowsErrorAndRetry();
    void setPreferenceHistorySuccessHidesErrorState();
    void syncTabHasPairButtonOpensDialog();
    void showConflictTabSelectsTab();
    void setSyncStatusUpdatesLabel();
    void syncTabRefreshButtonEmitsRequest();
    void setPeersPopulatesList();
    void setPeersShowsEmptyState();
    void revokeFlowOpensDialogAndConfirms();
    void setSyncSummaryUpdatesLabel();
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

    // 本机不提供解绑入口；非本机设备恰好一个“解绑”按钮。
    const QList<QPushButton *> revokeButtons =
        panel.findChildren<QPushButton *>(QStringLiteral("revokeButton"));
    QCOMPARE(revokeButtons.size(), 1);

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

void TestMemoryPanel::revokeFlowOpensDialogAndConfirms()
{
    MemoryPanel panel;
    QSignalSpy revokeSpy(&panel, &MemoryPanel::revokeConfirmed);

    panel.setPeers(QJsonArray{
        QJsonObject{
            {QStringLiteral("id"), QStringLiteral("dev_guest")},
            {QStringLiteral("name"), QStringLiteral("客厅一体机")},
            {QStringLiteral("is_self"), false},
            {QStringLiteral("status"), QStringLiteral("ONLINE")}}});

    QPushButton *revokeButton =
        panel.findChild<QPushButton *>(QStringLiteral("revokeButton"));
    QVERIFY(revokeButton != nullptr);
    QTest::mouseClick(revokeButton, Qt::LeftButton);

    RevokeDialog *dialog = panel.findChild<RevokeDialog *>();
    QVERIFY(dialog != nullptr);
    QVERIFY(dialog->isVisible());

    QPushButton *confirmButton =
        dialog->findChild<QPushButton *>(QStringLiteral("revokeConfirmButton"));
    QVERIFY(confirmButton != nullptr);
    QTest::mouseClick(confirmButton, Qt::LeftButton);

    QCOMPARE(revokeSpy.count(), 1);
    QCOMPARE(revokeSpy.takeFirst().at(0).toString(),
             QStringLiteral("dev_guest"));
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
