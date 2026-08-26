#include "app/MonitorController.h"

#include "app/AppSettings.h"

#include <QCoreApplication>
#include <QDateTime>

namespace {
MonitorLogEntry makeEntry(const QString &text)
{
    MonitorLogEntry entry;
    entry.timestamp = QDateTime::currentSecsSinceEpoch();
    entry.text = text;
    return entry;
}
} // namespace

const char *MonitorController::sourceKey(MonitorSource source)
{
    switch (source) {
    case MonitorSource::Directory: return "directory";
    case MonitorSource::Clipboard: return "clipboard";
    case MonitorSource::Behavior:  return "behavior";
    case MonitorSource::Screenshot: return "screenshot";
    }
    return "unknown";
}

QString MonitorController::sourceDisplayName(MonitorSource source)
{
    switch (source) {
    case MonitorSource::Directory:
        return QCoreApplication::translate("MonitorController",
                                           "目录文件监视");
    case MonitorSource::Clipboard:
        return QCoreApplication::translate("MonitorController", "剪贴板捕获");
    case MonitorSource::Behavior:
        return QCoreApplication::translate("MonitorController", "应用使用行为");
    case MonitorSource::Screenshot:
        return QCoreApplication::translate("MonitorController", "截屏识别");
    }
    return QString();
}

MonitorController::MonitorController(AppSettings *settings, QObject *parent)
    : QObject(parent)
    , m_settings(settings)
{
    // 信号参数跨队列连接 / QSignalSpy 传递需要按名注册元类型。
    qRegisterMetaType<MonitorSource>("MonitorSource");
    qRegisterMetaType<MonitorLogEntry>("MonitorLogEntry");
    load();
}

bool MonitorController::isSourceEnabled(MonitorSource source) const
{
    const int index = static_cast<int>(source);
    if (index < 0 || index >= sourceCount()) {
        return false;
    }
    return m_sources[index];
}

void MonitorController::load()
{
    m_enabled = m_settings->value(AppSettings::keyMonitorEnabled, false)
                    .toBool();
    // 「曾开启过」为单向粘性标记，跨实例恢复（见 hasEverBeenEnabled）。
    m_everEnabled =
        m_settings->value(AppSettings::keyMonitorEverEnabled, false).toBool();
    for (int i = 0; i < sourceCount(); ++i) {
        const QString key = AppSettings::keyMonitorSourcePrefix
                            + QLatin1String(sourceKey(static_cast<MonitorSource>(i)));
        m_sources[i] = m_settings->value(key, false).toBool();
    }
    m_directories = m_settings
                        ->value(AppSettings::keyMonitorDirectories)
                        .toStringList();
}

void MonitorController::setEnabled(bool on)
{
    if (m_enabled == on) {
        return;
    }
    m_enabled = on;
    m_settings->setValue(AppSettings::keyMonitorEnabled, on);
    // 首次开启时置位「曾开启过」并随本次变更一并落盘；关闭不清除。
    if (on && !m_everEnabled) {
        m_everEnabled = true;
        m_settings->setValue(AppSettings::keyMonitorEverEnabled, true);
    }
    m_settings->sync();
    appendLog(on ? QCoreApplication::translate("MonitorController", "监控已开启")
                 : QCoreApplication::translate("MonitorController", "监控已暂停"));
    emit enabledChanged(on);
}

void MonitorController::setSourceEnabled(MonitorSource source, bool on)
{
    const int index = static_cast<int>(source);
    if (index < 0 || index >= sourceCount()) {
        return;
    }
    if (m_sources[index] == on) {
        return;
    }
    m_sources[index] = on;
    const QString key = AppSettings::keyMonitorSourcePrefix
                        + QLatin1String(sourceKey(source));
    m_settings->setValue(key, on);
    m_settings->sync();
    // 活动日志记录开关状态变更（内存级，重启清零）。
    const QString name = sourceDisplayName(source);
    appendLog(on ? QCoreApplication::translate("MonitorController", "已开启：%1").arg(name)
                 : QCoreApplication::translate("MonitorController", "已暂停：%1").arg(name));
    emit sourceChanged(source, on);
}

void MonitorController::setDirectories(const QStringList &dirs)
{
    QStringList cleaned;
    for (const QString &dir : dirs) {
        const QString trimmed = dir.trimmed();
        if (!trimmed.isEmpty() && !cleaned.contains(trimmed)) {
            cleaned << trimmed;
        }
    }
    if (cleaned == m_directories) {
        return;
    }
    m_directories = cleaned;
    m_settings->setValue(AppSettings::keyMonitorDirectories, m_directories);
    m_settings->sync();
    emit directoriesChanged(m_directories);
}

void MonitorController::appendLog(const QString &text)
{
    const MonitorLogEntry entry = makeEntry(text);
    m_log.append(entry);
    emit logAppended(entry);
}
