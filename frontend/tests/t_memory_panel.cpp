#include <QJsonArray>
#include <QJsonObject>
#include <QLineEdit>
#include <QListWidget>
#include <QPushButton>
#include <QSignalSpy>
#include <QTabWidget>
#include <QTest>

#include "widgets/MemoryPanel.h"

// MemoryPanel 壳测试：三个 Tab 及标题。
class TestMemoryPanel : public QObject
{
    Q_OBJECT

private slots:
    void hasThreeTabs();
    void tabTitlesMatchPlan();
    void setConflictsPopulatesList();
    void setConflictsShowsEmptyState();
    void loadButtonEmitsHistoryRequested();
    void setPreferenceHistoryPopulatesList();
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

QTEST_MAIN(TestMemoryPanel)
#include "t_memory_panel.moc"
