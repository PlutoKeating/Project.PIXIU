#include "app/PixiuApp.h"

#include <QLoggingCategory>

Q_LOGGING_CATEGORY(lcApp, "pixiu.app")

// 私有实现：后续 feature（单实例、托盘、设置、服务与窗口）在此挂载。
struct PixiuApp::Private
{
    // Phase 1B 暂无成员；后续以 QScopedPointer 持有服务与窗口对象。
};

PixiuApp::PixiuApp(QObject *parent)
    : QObject(parent)
    , d(new Private())
{
}

PixiuApp::~PixiuApp() = default;

bool PixiuApp::start()
{
    qCInfo(lcApp) << "PIXIU application starting";

    // 后续 feature 在此创建服务与窗口（以 this 为 parent）。

    emit started();
    qCInfo(lcApp) << "PIXIU application started";
    return true;
}

void PixiuApp::shutdown()
{
    qCInfo(lcApp) << "PIXIU application shutting down";
    emit aboutToShutdown();
}
