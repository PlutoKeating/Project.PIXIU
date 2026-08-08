#include <QCoreApplication>
#include <QApplication>

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

    // 应用生命周期所有者：窗口与服务均由其统一管理。
    PixiuApp app;
    if (!app.start()) {
        return 1;
    }

    const int exitCode = application.exec();
    app.shutdown();
    return exitCode;
}
