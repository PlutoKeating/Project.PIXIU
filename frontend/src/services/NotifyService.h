#ifndef PIXIU_NOTIFY_SERVICE_H
#define PIXIU_NOTIFY_SERVICE_H

#include <QObject>
#include <QString>

class QSystemTrayIcon;

// 桌面通知服务：memory_ready/冲突/遗忘/同步事件 → 用户可见通知。
//
// 当前实现（普通 Qt 降级）：系统托盘可用时走 QSystemTrayIcon::showMessage；
// 托盘不可用（无桌面/headless 开发环境）时记录日志并返回 false，不阻塞调用方。
// Phase 7 在此接口下接入 kysdk-notification。
class NotifyService : public QObject
{
    Q_OBJECT

public:
    explicit NotifyService(QObject *parent = nullptr);

    // 绑定系统托盘图标；无托盘时通知降级为日志。
    void setTrayIcon(QSystemTrayIcon *tray);

    // 弹出通知。返回 true 表示已通过系统托盘展示；false 表示降级为日志记录。
    bool notify(const QString &title, const QString &body);

    // 当前是否具备真实通知能力。
    bool isAvailable() const;

private:
    QSystemTrayIcon *m_tray = nullptr;
};

#endif // PIXIU_NOTIFY_SERVICE_H
