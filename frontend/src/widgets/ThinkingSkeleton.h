#ifndef PIXIU_THINKING_SKELETON_H
#define PIXIU_THINKING_SKELETON_H

#include <QSize>
#include <QWidget>

class QVariantAnimation;

// 答案加载骨架屏：三条圆角灰条 + 呼吸脉冲动画。
//
// 对应 ARCHITECTURE §7.4“答案加载骨架屏”，替代纯文本“思考中…”占位；
// 视觉上轻量、可中断（新消息到达即被替换），无障碍名由 MessageList 设置。
class ThinkingSkeleton : public QWidget
{
    Q_OBJECT

public:
    explicit ThinkingSkeleton(QWidget *parent = nullptr);

    QSize sizeHint() const override;

protected:
    void paintEvent(QPaintEvent *event) override;

private:
    QVariantAnimation *m_pulse = nullptr;
    qreal m_alpha = 0.65;
};

#endif // PIXIU_THINKING_SKELETON_H
