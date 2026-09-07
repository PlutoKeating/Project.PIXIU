#include "services/BackendTransport.h"

BackendTransport::BackendTransport(QObject *parent)
    : QObject(parent)
{
}

BackendTransport::~BackendTransport() = default;

void BackendTransport::backendDiagnostics()
{
    emit errorOccurred(QStringLiteral("UNSUPPORTED"), tr("此传输不支持服务诊断"), QString());
}

void BackendTransport::memoryItem(const QString &, const QString &)
{
    emit errorOccurred(QStringLiteral("UNSUPPORTED"), tr("此传输不支持完整记忆读取"), QString());
}

void BackendTransport::memoryContext(const QJsonObject &)
{
    emit errorOccurred(QStringLiteral("UNSUPPORTED"), tr("此传输不支持版本化记忆召回"), QString());
}

void BackendTransport::updateMemory(const QJsonObject &)
{
    emit errorOccurred(QStringLiteral("UNSUPPORTED"), tr("此传输不支持记忆更新"), QString());
}

void BackendTransport::reviewedForget(const QJsonObject &)
{
    emit errorOccurred(QStringLiteral("UNSUPPORTED"), tr("此传输不支持安全遗忘"), QString());
}

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
