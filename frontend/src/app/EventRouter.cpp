#include "app/EventRouter.h"

#include <QLoggingCategory>

Q_LOGGING_CATEGORY(lcEvents, "pixiu.events")

EventRouter::EventRouter(QObject *parent)
    : QObject(parent)
{
}

void EventRouter::handleEvent(const QJsonObject &event)
{
    const QString name = event.value(QStringLiteral("event")).toString();
    if (name.isEmpty()) {
        qCWarning(lcEvents) << "ignoring event frame without 'event' field";
        return;
    }

    const QJsonValue dataValue = event.value(QStringLiteral("data"));
    if (!dataValue.isObject()) {
        // 脱敏诊断：只记录事件名与 data 状态，不输出原始 payload。
        const QString dataState =
            dataValue.isUndefined() ? QStringLiteral("missing")
                                    : QStringLiteral("non-object");
        qCWarning(lcEvents) << "ignoring event" << name << "with" << dataState << "data";
        return;
    }
    const QJsonObject data = dataValue.toObject();

    if (name == QStringLiteral("memory_ready")) {
        emit memoryReady(data);
        return;
    }
    if (name == QStringLiteral("conflict_detected")) {
        // B3-3 起 WS 帧携带 severity（low/medium/high，按 resolution 派生）；
        // 旧后端广播无此字段时缺省 high（最保守：宁可打扰不漏报）。
        const QString severity =
            data.value(QStringLiteral("severity")).toString();
        emit conflictDetected(
            data.value(QStringLiteral("knowledge_title")).toString(),
            data.value(QStringLiteral("field")).toString(),
            data.value(QStringLiteral("old_value")).toVariant().toString(),
            data.value(QStringLiteral("new_value")).toVariant().toString(),
            severity.isEmpty() ? QStringLiteral("high") : severity);
        return;
    }
    if (name == QStringLiteral("sync_event")) {
        emit syncEvent(data);
        return;
    }
    if (name == QStringLiteral("capture_event")) {
        // 契约保证 ts 为整数；兼容数值或可解析的整数文本。
        const QJsonValue tsValue = data.value(QStringLiteral("ts"));
        const qint64 ts =
            tsValue.isDouble() ? qint64(tsValue.toDouble())
                               : qint64(tsValue.toVariant().toLongLong());
        emit captureEvent(
            data.value(QStringLiteral("source")).toString(),
            data.value(QStringLiteral("status")).toString(),
            data.value(QStringLiteral("summary")).toString(),
            ts);
        return;
    }
    if (name == QStringLiteral("pair_request")) {
        emit pairingRequested(data);
        return;
    }

    // 未知事件：仅记录，保持前向兼容。
    qCInfo(lcEvents) << "ignoring unknown event:" << name;
}
