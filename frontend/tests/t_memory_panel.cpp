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

QTEST_MAIN(TestMemoryPanel)
#include "t_memory_panel.moc"
