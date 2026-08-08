#ifndef PIXIU_FLOATING_BALL_H
#define PIXIU_FLOATING_BALL_H

#include <QPoint>
#include <QWidget>

// 桌面悬浮球：半透明圆形常驻入口。
//
// 支持拖动、点击唤起聊天框；贴边收起与位置持久化由后续 feature 扩展。
// 本阶段不依赖 KylinSDK（普通 QWidget 实现，Phase 7 再接入 UKUI 能力）。
class FloatingBall : public QWidget
{
    Q_OBJECT

public:
    explicit FloatingBall(QWidget *parent = nullptr);

    QSize sizeHint() const override;

signals:
    // 无拖动位移的单击。
    void clicked();
    // 拖动结束后发射（供位置持久化）。
    void movedTo(const QPoint &topLeft);

protected:
    void paintEvent(QPaintEvent *event) override;
    void mousePressEvent(QMouseEvent *event) override;
    void mouseMoveEvent(QMouseEvent *event) override;
    void mouseReleaseEvent(QMouseEvent *event) override;

private:
    QPoint m_dragOffset;
    QPoint m_pressGlobalPos;
    bool m_wasDrag = false;

    static constexpr int kSize = 56;
    static constexpr int kDragThresholdPx = 4;
};

#endif // PIXIU_FLOATING_BALL_H
