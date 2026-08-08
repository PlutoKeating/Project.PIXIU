#ifndef PIXIU_SHORTCUT_MANAGER_H
#define PIXIU_SHORTCUT_MANAGER_H

#include <QObject>

class QWidget;
class QShortcut;

// 全局唤起快捷键管理。
//
// 开发态：使用 Qt ApplicationShortcut（Ctrl+Alt+P）唤起聊天框。
// 麒麟环境：Phase 7 以 kysdk-shortcut 替换实现，本类接口保持不变。
class ShortcutManager : public QObject
{
    Q_OBJECT

public:
    explicit ShortcutManager(QWidget *contextWidget, QObject *parent = nullptr);

    // 注册唤起快捷键；失败返回 false。
    bool registerToggleShortcut();

signals:
    void toggleRequested();

private:
    QWidget *m_contextWidget = nullptr;
    QShortcut *m_shortcut = nullptr;
};

#endif // PIXIU_SHORTCUT_MANAGER_H
