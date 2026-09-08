#include <QCoreApplication>
#include <QSignalSpy>
#include <QTest>
#include <QTranslator>
#include "../src/app/ProductInformation.h"

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
    QCOMPARE(QCoreApplication::translate("InputBar", "更多"),
             QStringLiteral("More"));
    QCOMPARE(QCoreApplication::translate("InputBar", "打开同步面板"),
             QStringLiteral("Open sync panel"));
    QCOMPARE(QCoreApplication::translate("InputBar", "录入图片或文件"),
             QStringLiteral("Import image or file"));
    QCOMPARE(QCoreApplication::translate("InputBar", "打开设置"),
             QStringLiteral("Open settings"));
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
    QCOMPARE(QCoreApplication::translate(
                 "CheckUpdateDialog",
                 "升级需要系统授权；您的记忆、配置和同步身份将被保留。"),
             QStringLiteral("System authorization is required. Your memories, "
                            "settings, and sync identity will be preserved."));
    QCOMPARE(QCoreApplication::translate(
                 "UpgradeController", "无法启动系统安装程序"),
             QStringLiteral("Unable to start the system installer."));
    QCOMPARE(QCoreApplication::translate(
                 "UpgradeController", "升级失败：%1"),
             QStringLiteral("Upgrade failed: %1"));
    QVERIFY(ProductInformation::about("test-version").startsWith("PIXIU test-version\n\nA memory workspace"));
    QVERIFY(ProductInformation::dataUse().contains("may be sent to the selected model service"));
    QVERIFY(ProductInformation::dataUse().contains("have been physically erased"));
    QVERIFY(ProductInformation::licenses().contains("This notice grants no new license"));
}

QTEST_MAIN(TestI18n)
#include "t_i18n.moc"
