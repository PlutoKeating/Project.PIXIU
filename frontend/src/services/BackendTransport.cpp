#include "services/BackendTransport.h"

BackendTransport::BackendTransport(QObject *parent)
    : QObject(parent)
{
}

BackendTransport::~BackendTransport() = default;

void BackendTransport::extractPreferences(const QJsonObject &)
{
    // 默认空实现：未实现偏好提取的传输忽略调用（测试桩友好）。
}
