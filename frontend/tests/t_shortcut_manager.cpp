#include <QtTest>

#include "app/ShortcutManager.h"

#include <QCoreApplication>
#include <QSignalSpy>
#include <QTest>
#include <QWidget>

// 快捷键测试固定编译 Qt 降级路径（见 CMakeLists 说明）：
// kysdk 全局快捷键依赖桌面会话，无法在 offscreen 测试中断言；
// 本测试覆盖注册、进程内激活与释放三个可确定性验证的行为。
class TestShortcutManager : public QObject
{
    Q_OBJECT

private slots:
    void registerToggleShortcutSucceeds();
    void activationEmitsToggleRequested();
    void releaseDisablesActivation();
    void releaseIsIdempotent();
};

void TestShortcutManager::registerToggleShortcutSucceeds()
{
    QWidget context;
    ShortcutManager manager(&context);
    QVERIFY(manager.registerToggleShortcut());
}

void TestShortcutManager::activationEmitsToggleRequested()
{
    QWidget context;
    context.show();
    QVERIFY(QTest::qWaitForWindowExposed(&context));

    ShortcutManager manager(&context);
    QVERIFY(manager.registerToggleShortcut());

    QSignalSpy spy(&manager, &ShortcutManager::toggleRequested);
    QTest::keyClick(&context, Qt::Key_P, Qt::ControlModifier | Qt::AltModifier);
    QCOMPARE(spy.count(), 1);
}

void TestShortcutManager::releaseDisablesActivation()
{
    QWidget context;
    context.show();
    QVERIFY(QTest::qWaitForWindowExposed(&context));

    ShortcutManager manager(&context);
    QVERIFY(manager.registerToggleShortcut());
    manager.releaseToggleShortcut();
    QCoreApplication::processEvents();

    QSignalSpy spy(&manager, &ShortcutManager::toggleRequested);
    QTest::keyClick(&context, Qt::Key_P, Qt::ControlModifier | Qt::AltModifier);
    QCOMPARE(spy.count(), 0);
}

void TestShortcutManager::releaseIsIdempotent()
{
    QWidget context;
    ShortcutManager manager(&context);
    QVERIFY(manager.registerToggleShortcut());

    manager.releaseToggleShortcut();
    manager.releaseToggleShortcut();
    QVERIFY(true);
}

QTEST_MAIN(TestShortcutManager)

#include "t_shortcut_manager.moc"
