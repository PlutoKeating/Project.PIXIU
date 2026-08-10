#include <QCoreApplication>
#include <QSignalSpy>
#include <QTest>
#include <QTranslator>

// i18n 资源测试：内嵌英文翻译可从 qrc 加载并生效。
class TestI18n : public QObject
{
    Q_OBJECT

private slots:
    void englishTranslationLoadsAndApplies();
};

void TestI18n::englishTranslationLoadsAndApplies()
{
    QTranslator translator;
    QVERIFY2(translator.load(QStringLiteral(":/i18n/pixiu_en_US.qm")),
             "embedded en_US translation must be present in qrc");
    QCoreApplication::installTranslator(&translator);

    QCOMPARE(QCoreApplication::translate("InputBar", "记忆"),
             QStringLiteral("Memory"));
    QCOMPARE(QCoreApplication::translate("InputBar", "发送"),
             QStringLiteral("Send"));
    QCOMPARE(QCoreApplication::translate("ForgetDialog", "取消"),
             QStringLiteral("Cancel"));
    QCOMPARE(QCoreApplication::translate("MessageList", "思考中…"),
             QStringLiteral("Thinking…"));
    QCOMPARE(QCoreApplication::translate("MessageList", "重试"),
             QStringLiteral("Retry"));
    QCOMPARE(QCoreApplication::translate("MessageList", "录入知识"),
             QStringLiteral("Import knowledge"));
    QCOMPARE(QCoreApplication::translate("InputBar", "打开记忆面板"),
             QStringLiteral("Open memory panel"));
    QCOMPARE(QCoreApplication::translate("ChatWindow", "置顶"),
             QStringLiteral("Pin to top"));
    QCOMPARE(QCoreApplication::translate("ChatWindow", "您可以问我："),
             QStringLiteral("You can ask me:"));
    QCOMPARE(QCoreApplication::translate("InputBar", "更多"),
             QStringLiteral("More"));
    QCOMPARE(QCoreApplication::translate("InputBar", "打开同步面板"),
             QStringLiteral("Open sync panel"));
    QCOMPARE(QCoreApplication::translate("InputBar", "录入图片或文件"),
             QStringLiteral("Import image or file"));
    QCOMPARE(QCoreApplication::translate("FloatingBall", "打开聊天框"),
             QStringLiteral("Open chat window"));
    QCOMPARE(QCoreApplication::translate("FloatingBall", "退出"),
             QStringLiteral("Quit"));
    QCOMPARE(QCoreApplication::translate("FloatingBall", "设置"),
             QStringLiteral("Settings"));
    QCOMPARE(QCoreApplication::translate("InputBar", "打开设置"),
             QStringLiteral("Open settings"));
    QCOMPARE(QCoreApplication::translate("SettingsDialog", "界面语言"),
             QStringLiteral("Language"));
    QCOMPARE(QCoreApplication::translate("SettingsDialog", "跟随系统"),
             QStringLiteral("Follow system"));
    QCOMPARE(QCoreApplication::translate("SettingsDialog", "全局快捷键"),
             QStringLiteral("Global shortcut"));
    QCOMPARE(QCoreApplication::translate("SettingsDialog",
             "快捷键需包含 Ctrl / Alt / Meta 修饰键；修改后立即生效。"),
             QStringLiteral("Shortcut must include a Ctrl / Alt / Meta "
                            "modifier; changes apply immediately."));
    QCOMPARE(QCoreApplication::translate("MemoryPanel", "重试"),
             QStringLiteral("Retry"));
    QCOMPARE(QCoreApplication::translate("MemoryPanel", "正在加载…"),
             QStringLiteral("Loading…"));
    QCOMPARE(QCoreApplication::translate("MemoryPanel", "提取偏好"),
             QStringLiteral("Extract preferences"));
    QCOMPARE(QCoreApplication::translate("PixiuApp", "冲突加载失败（%1）：%2"),
             QStringLiteral("Conflict load failed (%1): %2"));
    QCOMPARE(QCoreApplication::translate(
                 "PixiuApp", "上一条记忆仍在写入，本次录入已跳过，请稍候重试。"),
             QStringLiteral("Previous memory is still being stored; this "
                            "import was skipped. Please retry shortly."));
    QCOMPARE(QCoreApplication::translate(
                 "PixiuApp", "后端服务未连接，请先启动 PIXIU 后端服务后重试。"),
             QStringLiteral("Backend service is offline. Please start the "
                            "PIXIU backend service and retry."));
}

QTEST_MAIN(TestI18n)
#include "t_i18n.moc"
