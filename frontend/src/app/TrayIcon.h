#ifndef PIXIU_TRAY_ICON_H
#define PIXIU_TRAY_ICON_H

#include <QObject>

class QSystemTrayIcon;

// 系统托盘入口：提供显示主窗口与显式退出两个动作。
//
// 本阶段不承载悬浮球、桌面通知或记忆事件角标（分别属于后续 feature）。
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

signals:
    // 用户点击“打开 PIXIU 主窗口”。
    void openRequested();
    // 用户点击“退出”。
    void quitRequested();

private:
    void buildMenu();

    QSystemTrayIcon *m_tray = nullptr;
};

#endif // PIXIU_TRAY_ICON_H
