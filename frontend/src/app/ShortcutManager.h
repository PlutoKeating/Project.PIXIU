#ifndef PIXIU_SHORTCUT_MANAGER_H
#define PIXIU_SHORTCUT_MANAGER_H

#include <QKeySequence>
#include <QObject>

class QWidget;
class QShortcut;
class QTimer;

// 全局唤起快捷键管理。
//
// 麒麟环境（PIXIU_HAVE_KYSDK）：使用 kysdk-shortcut 注册系统级全局快捷键。
// 按键由桌面接管，按下时拉起本应用可执行程序；重复实例由宿主单实例协议
// 转发激活给主实例，因此全局快捷键路径不产生进程内
// toggleRequested 信号。
// SDK 服务缺失时按官方入口启动，等待就绪期间保持应用内降级；不停止共享服务。
// 开发态/降级（无 KYSDK 或注册失败）：使用 Qt ApplicationShortcut
// （Ctrl+Alt+P）请求显示宿主，toggleRequested 在进程内发出；不是系统级唤起。
class ShortcutManager : public QObject
{
    Q_OBJECT

public:
    explicit ShortcutManager(QWidget *contextWidget, QObject *parent = nullptr);
    ~ShortcutManager() override;

    // 注册唤起快捷键（默认 Ctrl+Alt+P）；空序列回退默认值；失败返回 false。
    bool registerToggleShortcut(
        const QKeySequence &sequence = QKeySequence(QStringLiteral("Ctrl+Alt+P")));

    // 释放已注册的快捷键（KYSDK 全局快捷键与 Qt 降级快捷键）；可重复调用。
    void releaseToggleShortcut();

    // 最近一次注册的序列（用于变化检测/测试）。
    QKeySequence currentSequence() const;
    // 注册已取得且官方会话服务就绪，不只是 SDK 创建接口返回成功。
    bool isGlobal() const { return m_globalAvailable; }

signals:
    void toggleRequested();
    void availabilityChanged(bool global);

#ifdef PIXIU_HAVE_KYSDK
protected:
    // Platform seam: SDK registration and the session service are distinct.
    virtual bool kylinServiceReady() const;
    virtual bool startKylinService();
    void updateKylinServiceState();
#endif

private:
    bool installFallback();
    void setGlobalAvailable(bool available);
#ifdef PIXIU_HAVE_KYSDK
    bool registerKylinGlobalShortcut();
    QTimer *m_servicePoll = nullptr;
    int m_serviceChecks = 0;
#endif

    QWidget *m_contextWidget = nullptr;
    QShortcut *m_shortcut = nullptr;
    QKeySequence m_sequence;
    bool m_globalRegistered = false;
    bool m_globalAvailable = false;
};

#endif // PIXIU_SHORTCUT_MANAGER_H
