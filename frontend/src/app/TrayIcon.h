#ifndef PIXIU_TRAY_ICON_H
#define PIXIU_TRAY_ICON_H

#include <QObject>

class QAction;
class QSystemTrayIcon;

// 系统托盘入口：提供显示主窗口、暂停/继续监控与显式退出等动作。
//
// 悬浮球、桌面通知与记忆事件角标由各自 feature 承载。
// 托盘不可用（如无系统托盘的服务环境）时静默降级，不阻塞应用启动。
class TrayIcon : public QObject
{
    Q_OBJECT

public:
    explicit TrayIcon(QObject *parent = nullptr);

    // 显示托盘图标；托盘不可用时返回 false。
    bool show();

    // 隐藏托盘图标。
    void hide();

    // 底层 QSystemTrayIcon（供 NotifyService 展示通知）；无托盘时为 nullptr。
    QSystemTrayIcon *trayIcon() const;

    // 更新暂停动作文案（监控开启显示“暂停监控”，暂停中显示“继续监控”）。
    void setPauseActionText(const QString &text);

signals:
    // 用户点击“打开 PIXIU 主窗口”。
    void openRequested();
    // 用户点击“暂停/继续监控”。
    void pauseMonitorRequested();
    // 用户点击“退出”。
    void quitRequested();

private:
    void buildMenu();

    QSystemTrayIcon *m_tray = nullptr;
    QAction *m_pauseAction = nullptr;
};

#endif // PIXIU_TRAY_ICON_H
