#include <QCoreApplication>
#include <QApplication>
#include <QFile>
#include <QIcon>
#include <QLocale>
#include <QTranslator>

#include "app/PixiuApp.h"

int main(int argc, char *argv[])
{
    // 高 DPI 与多屏：必须在 QApplication 构造前启用，保证逻辑坐标按设备
    // 独立像素计算；UKUI 高分屏下控件与图标按缩放系数正确呈现。
    QApplication::setAttribute(Qt::AA_EnableHighDpiScaling);
    QApplication::setAttribute(Qt::AA_UseHighDpiPixmaps);

    QApplication application(argc, argv);

    QCoreApplication::setApplicationName(QStringLiteral("PIXIU"));
    QCoreApplication::setApplicationVersion(QStringLiteral("0.1.0"));
    QCoreApplication::setOrganizationName(QStringLiteral("Project.PIXIU"));
    // 应用窗口/任务栏图标：内嵌 pixiu.svg（desktop 入口与托盘共用同一资源）。
    application.setWindowIcon(QIcon(QStringLiteral(":/icons/pixiu.svg")));

    // 语言本地化：英文环境加载内嵌翻译，其余环境保持中文源码文本。
    QTranslator translator;
    // 麒麟/桌面环境可能通过 LANGUAGE 优先指定界面语言，QLocale::system()
    // 在本机优先读取 LANGUAGE；这里同时兼容 LANGUAGE/LANG/系统语言。
    const QLocale systemLocale = QLocale::system();
    const QString languageEnv = qEnvironmentVariable("LANGUAGE");
    const bool englishLocale =
        systemLocale.language() == QLocale::English
        || systemLocale.name().startsWith(QLatin1String("en"), Qt::CaseInsensitive)
        || languageEnv.startsWith(QLatin1String("en"), Qt::CaseInsensitive);
    if (englishLocale
        && translator.load(QStringLiteral(":/i18n/pixiu_en_US.qm"))) {
        QCoreApplication::installTranslator(&translator);
        qInfo() << "translation loaded for" << systemLocale.name();
    }

    // 主题感知样式：颜色全部取 palette 角色，明暗主题切换时随 Palette 联动。
    QFile styleFile(QStringLiteral(":/styles.qss"));
    if (styleFile.open(QIODevice::ReadOnly | QIODevice::Text)) {
        application.setStyleSheet(QString::fromUtf8(styleFile.readAll()));
    }

    // 应用生命周期所有者：窗口与服务均由其统一管理。
    PixiuApp app;
    if (!app.start()) {
        return 1;
    }

    const int exitCode = application.exec();
    app.shutdown();
    return exitCode;
}
