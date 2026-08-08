#ifndef PIXIU_FLOATING_BALL_H
#define PIXIU_FLOATING_BALL_H

#include <QPoint>
#include <QWidget>

class QScreen;

// 桌面悬浮球：半透明圆形常驻入口。
//
// 支持拖动、点击唤起聊天框、贴边收起（悬停展开）与位置恢复。
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

signals:
    // 无拖动位移的单击。
    void clicked();
    // 拖动结束、贴边收起或悬停展开后发射（供位置持久化）。
    void movedTo(const QPoint &topLeft);

protected:
    void paintEvent(QPaintEvent *event) override;
    void mousePressEvent(QMouseEvent *event) override;
    void mouseMoveEvent(QMouseEvent *event) override;
    void mouseReleaseEvent(QMouseEvent *event) override;
    void enterEvent(QEvent *event) override;
    void leaveEvent(QEvent *event) override;

private:
    QScreen *screenFor(const QPoint &globalPos) const;
    void snapToEdge();
    void collapseToEdge();
    void expandFromEdge();

    QPoint m_dragOffset;
    QPoint m_pressGlobalPos;
    bool m_wasDrag = false;
    QPoint m_expandedPos;
    bool m_collapsed = false;
    int m_unreadCount = 0;

    static constexpr int kDragThresholdPx = 4;
    static constexpr int kEdgeSnapPx = 12;
    static constexpr qreal kCollapsedVisibleRatio = 1.0 / 3.0;
};

#endif // PIXIU_FLOATING_BALL_H
