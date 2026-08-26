#ifndef PIXIU_FLOATING_BALL_H
#define PIXIU_FLOATING_BALL_H

#include <QPoint>
#include <QWidget>

class QAction;
class QContextMenuEvent;
class QMenu;
class QScreen;
class QVariantAnimation;

// 桌面悬浮球：半透明圆形常驻入口。
//
// 支持鼠标左键拖拽自由移动（小球停留在用户放置的位置）、点击唤起聊天框
// 与位置恢复；默认初始位于屏幕可用区域右下角。
// 本阶段不依赖 KylinSDK（普通 QWidget 实现，Phase 7 再接入 UKUI 能力）。
class FloatingBall : public QWidget
{
    Q_OBJECT

public:
    explicit FloatingBall(QWidget *parent = nullptr);

    QSize sizeHint() const override;

    static constexpr int kSize = 56;

    // 恢复到保存位置；位置越界时钳制到最近屏幕的有效区域。
    void restorePosition(const QPoint &savedPos);

    // 未读业务事件数（memory_ready 等触发的右上角标）。
    int unreadCount() const;
    void setUnreadCount(int count);
    void clearUnread();

    // 更新暂停菜单文案（监控开启显示“暂停监控”，暂停中显示“继续监控”）。
    void setPauseMenuText(const QString &text);

signals:
    // 无拖动位移的单击。
    void clicked();
    // 右键菜单“设置”。
    void settingsRequested();
    // 右键菜单“记忆面板”。
    void openPanelRequested();
    // 右键菜单“监控中心”。
    void monitorCenterRequested();
    // 右键菜单“暂停/继续监控”。
    void pauseMonitorRequested();
    // 右键菜单“退出”。
    void quitRequested();
    // 拖动结束或位置恢复后发射（供位置持久化）。
    void movedTo(const QPoint &topLeft);

protected:
    void paintEvent(QPaintEvent *event) override;
    void mousePressEvent(QMouseEvent *event) override;
    void mouseMoveEvent(QMouseEvent *event) override;
    void mouseReleaseEvent(QMouseEvent *event) override;
    void contextMenuEvent(QContextMenuEvent *event) override;

private:
    void buildContextMenu();
    QScreen *screenFor(const QPoint &globalPos) const;

    QPoint m_dragOffset;
    QPoint m_pressGlobalPos;
    bool m_wasDrag = false;
    int m_unreadCount = 0;
    QAction *m_pauseAction = nullptr;
    QMenu *m_contextMenu = nullptr;
    QVariantAnimation *m_badgePulseAnim = nullptr;
    qreal m_badgePulse = 1.0;

    void startBadgePulse();
    static constexpr int kDragThresholdPx = 4;
};

#endif // PIXIU_FLOATING_BALL_H
