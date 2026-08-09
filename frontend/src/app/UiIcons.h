#ifndef PIXIU_UI_ICONS_H
#define PIXIU_UI_ICONS_H

#include <QColor>
#include <QApplication>
#include <QGuiApplication>
#include <QIcon>
#include <QPainter>
#include <QPainterPath>
#include <QPalette>
#include <QPixmap>
#include <QPolygonF>
#include <QtMath>

// 运行时绘制的主题感知图标（header-only）。
//
// 设计约束（ARCHITECTURE §7.5）：图标颜色取自应用 Palette，随 UKUI 明暗
// 主题切换；多倍图按当前设备像素比生成，保证 HiDPI 下清晰。控件持有图标
// 时监听 QApplication::paletteChanged 重建即可，无需 SVG 明暗两套资源。
namespace ui {

namespace detail {

constexpr qreal kPi = 3.14159265358979323846;

// 以 24 单位逻辑坐标系绘制一个简洁齿轮（8 齿，中心镂空）。
inline QPainterPath gearPath()
{
    const QPointF center(12.0, 12.0);
    const qreal outer = 10.2;
    const qreal inner = 7.6;
    const int teeth = 8;

    QPolygonF star;
    for (int i = 0; i < teeth * 2; ++i) {
        const qreal angle = i * kPi / teeth;
        const qreal radius = (i % 2 == 0) ? outer : inner;
        star << QPointF(center.x() + qCos(angle) * radius,
                        center.y() + qSin(angle) * radius);
    }

    QPainterPath path;
    path.addPolygon(star);
    path.addEllipse(center, 3.2, 3.2);
    path.setFillRule(Qt::OddEvenFill);
    return path;
}

inline void paintGear(QPainter *painter, const QColor &color, const QRectF &rect)
{
    painter->save();
    painter->translate(rect.topLeft());
    painter->scale(rect.width() / 24.0, rect.height() / 24.0);
    painter->setRenderHint(QPainter::Antialiasing);
    painter->setPen(Qt::NoPen);
    painter->setBrush(color);
    painter->drawPath(gearPath());
    painter->restore();
}

} // namespace detail

// 齿轮图标（设置入口）：颜色取自传入 Palette 的 Text 角色。
inline QIcon gearIcon(const QColor &color)
{
    QIcon icon;
    const qreal dpr = qMax(qreal(1.0), qApp->devicePixelRatio());
    const int sizes[] = {16, 24, 32};
    for (int size : sizes) {
        QPixmap pixmap(qRound(size * dpr), qRound(size * dpr));
        pixmap.setDevicePixelRatio(dpr);
        pixmap.fill(Qt::transparent);
        QPainter painter(&pixmap);
        detail::paintGear(&painter, color, QRectF(0, 0, size, size));
        icon.addPixmap(pixmap);
    }
    return icon;
}

inline QIcon gearIcon(const QPalette &palette)
{
    return gearIcon(palette.color(QPalette::Text));
}

} // namespace ui

#endif // PIXIU_UI_ICONS_H
