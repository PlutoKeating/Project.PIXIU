#ifndef PIXIU_MONITOR_CONTROLLER_H
#define PIXIU_MONITOR_CONTROLLER_H

#include <QMetaType>
#include <QObject>
#include <QString>
#include <QStringList>
#include <QVector>

class AppSettings;

// 监控数据源种类。批次①只承载配置状态；真实采集器在批次②接入。
enum class MonitorSource
{
    Directory,   // 目录文件监视
    Clipboard,   // 剪贴板捕获
    Behavior,    // 应用使用行为
    Screenshot,  // 截屏识别
};

struct MonitorLogEntry
{
    qint64 timestamp = 0;  // Unix 秒
    QString text;
};

// 信号参数经队列/信号监视器传递时需要元类型注册。
Q_DECLARE_METATYPE(MonitorSource)
Q_DECLARE_METATYPE(MonitorLogEntry)

// 监控状态控制器：全局开关 + 数据源开关 + 监视目录清单 + 本地活动日志。
//
// 批次①为纯本地实现：状态经 AppSettings 持久化；活动日志只记录本机状态
// 变更且不持久化（重启清零）。真实捕获事件流与远端日志查询由
// frontend/docs/MONITOR_API_REQUIREMENTS.md 定义的 /monitor/* 契约在
// 批次②替换/补充。
class MonitorController : public QObject
{
    Q_OBJECT

public:
    explicit MonitorController(AppSettings *settings,
                               QObject *parent = nullptr);

    bool isEnabled() const { return m_enabled; }
    // 是否曾开启过监控（持久化粘性标记，关闭监控不清除）。
    // 用途：UI 徽标仅在「曾开启过 + 当前关闭」时提示“⏸ 已暂停”；
    // 从未启用过的用户（默认关闭）界面保持干净。
    bool hasEverBeenEnabled() const { return m_everEnabled; }
    bool isSourceEnabled(MonitorSource source) const;
    QStringList directories() const { return m_directories; }

    // 全局总闸：关闭时所有数据源停止捕获（状态各自保留，恢复总闸即还原）。
    void setEnabled(bool on);
    void setSourceEnabled(MonitorSource source, bool on);
    void setDirectories(const QStringList &dirs);

    QVector<MonitorLogEntry> log() const { return m_log; }
    void appendLog(const QString &text);

    static int sourceCount() { return 4; }
    static const char *sourceKey(MonitorSource source);  // 设置键后缀

    // 数据源的用户可读中文名称（日志与监控中心面板共用的单一文案来源）。
    static QString sourceDisplayName(MonitorSource source);

signals:
    void enabledChanged(bool on);
    void sourceChanged(MonitorSource source, bool on);
    void directoriesChanged(const QStringList &dirs);
    void logAppended(const MonitorLogEntry &entry);

private:
    void load();

    AppSettings *m_settings = nullptr;
    bool m_enabled = false;
    bool m_everEnabled = false;  // 曾开启过监控（持久化，单向置位）
    bool m_sources[4] = {false, false, false, false};
    QStringList m_directories;
    QVector<MonitorLogEntry> m_log;
};

#endif // PIXIU_MONITOR_CONTROLLER_H
