#ifndef PIXIU_MONITOR_CENTER_DIALOG_H
#define PIXIU_MONITOR_CENTER_DIALOG_H

#include <QDialog>
#include <QList>

class QCheckBox;
class QLineEdit;
class QListWidget;
class QTabWidget;

class MonitorController;

// 监控中心：「被动监控」的用户掌控面。
//   Tab1 数据源 —— 主开关 + 四类数据源开关矩阵 + 监视目录清单（增删）；
//   Tab2 活动记录 —— 只读日志列表（当前为本机状态变更，批次②接远端事件）。
// 直接读写注入的 MonitorController，不持有独立状态。
class MonitorCenterDialog : public QDialog
{
    Q_OBJECT

public:
    explicit MonitorCenterDialog(MonitorController *controller,
                                 QWidget *parent = nullptr);

    void showAndFocus();

private slots:
    void onMasterToggled(bool on);
    void onAddDirectory();
    void onRemoveDirectory();
    void reloadLog();

private:
    void rebuildDirectoryList();

    MonitorController *m_controller = nullptr;
    QCheckBox *m_masterCheck = nullptr;
    QList<QCheckBox *> m_sourceChecks;
    QLineEdit *m_dirEdit = nullptr;
    QListWidget *m_dirList = nullptr;
    QListWidget *m_logList = nullptr;
    QTabWidget *m_tabs = nullptr;
};

#endif // PIXIU_MONITOR_CENTER_DIALOG_H
