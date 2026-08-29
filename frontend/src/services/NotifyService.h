#ifndef PIXIU_NOTIFY_SERVICE_H
#define PIXIU_NOTIFY_SERVICE_H

#include <QObject>
#include <QString>

class QSystemTrayIcon;

namespace kdk {
class KNotifier;
}

// 桌面通知服务：memory_ready/冲突/遗忘/同步事件 → 用户可见通知。
//
// 麒麟环境（PIXIU_HAVE_KYSDK）：通过 kysdk-notification 的 KNotifier 弹出
// 系统通知；通知不依赖托盘。
// 开发态/降级（无 KYSDK）：系统托盘可用时走 QSystemTrayIcon::showMessage；
// 托盘不可用（无桌面/headless 开发环境）时记录日志并返回 false，不阻塞调用方。
class NotifyService : public QObject
{
    Q_OBJECT

public:
    explicit NotifyService(QObject *parent = nullptr);

    // 绑定系统托盘图标；无托盘时通知降级为日志。
    void setTrayIcon(QSystemTrayIcon *tray);

    // 弹出通知。返回 true 表示已通过系统托盘展示；false 表示降级为日志记录。
    // virtual：测试经 PixiuApp::setNotifyServiceForTest 注入记录型子类，
    // 断言 F3-1 打扰分级发出的通知标题/正文。
    virtual bool notify(const QString &title, const QString &body);

    // 当前是否具备真实通知能力。
    bool isAvailable() const;

private:
#ifdef PIXIU_HAVE_KYSDK
    kdk::KNotifier *m_notifier = nullptr;
#endif
    QSystemTrayIcon *m_tray = nullptr;
};

#endif // PIXIU_NOTIFY_SERVICE_H
