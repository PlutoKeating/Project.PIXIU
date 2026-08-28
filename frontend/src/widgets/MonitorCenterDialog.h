#ifndef PIXIU_MONITOR_CENTER_DIALOG_H
#define PIXIU_MONITOR_CENTER_DIALOG_H

#include <QDialog>
#include <QJsonArray>
#include <QList>
#include <QSet>
#include <QString>

class QCheckBox;
class QLabel;
class QLineEdit;
class QListWidget;
class QTabWidget;

class MonitorController;

// 监控中心：「被动监控」的用户掌控面。
//   Tab1 数据源 —— 主开关 + 四类数据源开关矩阵 + 监视目录清单（增删）；
//   Tab2 活动记录 —— 只读日志列表（本机状态变更 + 远端分页记录 + 实时
//   capture_event 追加）。
// 直接读写注入的 MonitorController，不持有独立配置状态；远端配置/日志
// 经 configEdited / logPageRequested 信号交由 PixiuApp 走 transport 上送/
// 拉取（A-3：远端配置优先、本地键离线回退）。
class MonitorCenterDialog : public QDialog
{
    Q_OBJECT

public:
    explicit MonitorCenterDialog(MonitorController *controller,
                                 QWidget *parent = nullptr);

    void showAndFocus();

    // 渲染服务端分页记录（条目形状 {ts,source,status,summary,evidence_id,
    // knowledge_id}）；显示「[MM-dd HH:mm] 文案」，无 id 的条目省略 id 部分。
    void appendRemoteLog(const QJsonArray &entries);
    // capture_event 实时追加，与本地日志同列表；同源重复事件只渲染一次。
    void appendCaptureEvent(const QString &source, const QString &status,
                            const QString &summary, qint64 ts);
    // 离线提示：配置上送失败时状态行显示「离线，仅本地生效」，恢复后隐藏。
    void setOfflineHint(bool offline);

signals:
    // 面板内任一配置改动（主开关/源开关/目录增删）后触发；
    // PixiuApp 以此为唯一 PUT 上送点，避免重复上送。
    void configEdited();
    // 活动记录首页懒加载请求（首次打开面板或活动记录 Tab 时触发一次）。
    void logPageRequested(int limit, int offset);

private slots:
    void onMasterToggled(bool on);
    void onAddDirectory();
    void onRemoveDirectory();
    void reloadLog();

private:
    void rebuildDirectoryList();
    void requestFirstLogPage();
    void appendLogLine(qint64 ts, const QString &source,
                       const QString &summary, const QString &idsSuffix);

    MonitorController *m_controller = nullptr;
    QCheckBox *m_masterCheck = nullptr;
    QList<QCheckBox *> m_sourceChecks;
    QLineEdit *m_dirEdit = nullptr;
    QListWidget *m_dirList = nullptr;
    QListWidget *m_logList = nullptr;
    QTabWidget *m_tabs = nullptr;
    QLabel *m_offlineHint = nullptr;
    // 活动记录首页是否已懒加载（防重复请求与重复渲染）。
    bool m_remoteLogLoaded = false;
    // 已渲染条目的去重键（ts|source|summary）：远端分页与实时 WS 可能
    // 重复送达同一事件，只追加一次。
    QSet<QString> m_logKeys;
};

#endif // PIXIU_MONITOR_CENTER_DIALOG_H
