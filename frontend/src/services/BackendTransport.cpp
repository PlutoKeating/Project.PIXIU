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

void BackendTransport::preferencesList(const QString &)
{
}

void BackendTransport::evidenceDetail(const QString &)
{
}

void BackendTransport::createPairingToken(const QJsonObject &)
{
}

void BackendTransport::monitorConfig()
{
}

void BackendTransport::updateMonitorConfig(const QJsonObject &)
{
}

void BackendTransport::monitorLog(int, int)
{
}

void BackendTransport::discoverDevices()
{
}

void BackendTransport::requestPairing(const QString &)
{
}

void BackendTransport::confirmPairing(const QString &, bool)
{
}

void BackendTransport::updateSyncSettings(bool, bool)
{
}

void BackendTransport::deliveryInsights()
{
}

void BackendTransport::deliveryDigest()
{
}
