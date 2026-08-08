#include <QJsonArray>
#include <QJsonObject>
#include <QListWidget>
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

    QListWidget *list = panel.findChild<QListWidget *>();
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

    QListWidget *list = panel.findChild<QListWidget *>();
    QVERIFY(list != nullptr);
    QCOMPARE(list->count(), 0);
    QVERIFY(list->isHidden());
}

QTEST_MAIN(TestMemoryPanel)
#include "t_memory_panel.moc"
