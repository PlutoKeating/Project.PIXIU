#ifndef PIXIU_SHORTCUT_MANAGER_H
#define PIXIU_SHORTCUT_MANAGER_H

#include <QKeySequence>
#include <QObject>

class QWidget;
class QShortcut;

// 全局唤起快捷键管理。
//
// 麒麟环境（PIXIU_HAVE_KYSDK）：使用 kysdk-shortcut 注册系统级全局快捷键。
// 按键由桌面接管，按下时拉起本应用可执行程序；重复实例由宿主单实例协议
// 转发激活给主实例，因此全局快捷键路径不产生进程内
// toggleRequested 信号。
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
    bool isGlobal() const { return m_globalRegistered; }

signals:
    void toggleRequested();

private:
#ifdef PIXIU_HAVE_KYSDK
    bool registerKylinGlobalShortcut();
#endif

    QWidget *m_contextWidget = nullptr;
    QShortcut *m_shortcut = nullptr;
    QKeySequence m_sequence;
    bool m_globalRegistered = false;
};

#endif // PIXIU_SHORTCUT_MANAGER_H
