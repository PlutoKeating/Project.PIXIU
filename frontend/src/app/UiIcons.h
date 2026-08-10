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
#include <QPen>
#include <QPointF>
#include <QRectF>
#include <QtMath>
#include <functional>

// 运行时绘制的主题感知图标（header-only）。
//
// 设计约束（ARCHITECTURE §7.5）：图标颜色取自应用 Palette，随 UKUI 明暗
// 主题切换；多倍图按当前设备像素比生成，保证 HiDPI 下清晰。控件持有图标
// 时监听 QApplication::paletteChanged 重建即可，无需 SVG 明暗两套资源。
namespace ui {

namespace detail {

constexpr qreal kPi = 3.14159265358979323846;

// 通用图标渲染器：以 24 单位逻辑坐标系绘制，按当前设备像素比生成 16/24/32
// 多倍图（HiDPI 清晰）。绘制函数只负责在传入的 24×24 矩形内作画。
using IconPainter = std::function<void(QPainter &, const QRectF &)>;

inline QIcon makeIcon(const IconPainter &draw)
{
    QIcon icon;
    const qreal dpr = qMax(qreal(1.0), qApp->devicePixelRatio());
    const int sizes[] = {16, 24, 32};
    for (int size : sizes) {
        QPixmap pixmap(qRound(size * dpr), qRound(size * dpr));
        pixmap.setDevicePixelRatio(dpr);
        pixmap.fill(Qt::transparent);
        QPainter painter(&pixmap);
        painter.setRenderHint(QPainter::Antialiasing);
        draw(painter, QRectF(0, 0, size, size));
        icon.addPixmap(pixmap);
    }
    return icon;
}

inline void beginIconFrame(QPainter *painter, const QRectF &rect)
{
    painter->save();
    painter->translate(rect.topLeft());
    const qreal scale = rect.width() / 24.0;
    painter->scale(scale, scale);
    painter->setRenderHint(QPainter::Antialiasing);
}

inline QPen iconPen(const QColor &color, qreal width = 1.8)
{
    return QPen(color, width, Qt::SolidLine, Qt::RoundCap, Qt::RoundJoin);
}

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
    return detail::makeIcon([color](QPainter &painter, const QRectF &rect) {
        detail::paintGear(&painter, color, rect);
    });
}

inline QIcon gearIcon(const QPalette &palette)
{
    return gearIcon(palette.color(QPalette::Text));
}

// 置顶（图钉）：未置顶为线框、已置顶为实心。
inline QIcon pinIcon(const QColor &color, bool filled)
{
    return detail::makeIcon([color, filled](QPainter &painter, const QRectF &rect) {
        detail::beginIconFrame(&painter, rect);
        QPainterPath path;
        path.addEllipse(QPointF(12.0, 9.0), 4.6, 4.6);
        QPolygonF tip;
        tip << QPointF(7.4, 9.0) << QPointF(12.0, 21.0) << QPointF(16.6, 9.0);
        path.addPolygon(tip);
        if (filled) {
            painter.setPen(Qt::NoPen);
            painter.setBrush(color);
        } else {
            painter.setBrush(Qt::NoBrush);
            painter.setPen(detail::iconPen(color));
        }
        painter.drawPath(path);
        painter.restore();
    });
}

inline QIcon pinIcon(const QPalette &palette, bool filled)
{
    return pinIcon(palette.color(QPalette::Text), filled);
}

// 更多（三个圆点）。
inline QIcon moreIcon(const QColor &color)
{
    return detail::makeIcon([color](QPainter &painter, const QRectF &rect) {
        detail::beginIconFrame(&painter, rect);
        painter.setPen(Qt::NoPen);
        painter.setBrush(color);
        for (qreal x : {6.0, 12.0, 18.0}) {
            painter.drawEllipse(QPointF(x, 12.0), 1.9, 1.9);
        }
        painter.restore();
    });
}

inline QIcon moreIcon(const QPalette &palette)
{
    return moreIcon(palette.color(QPalette::Text));
}

// 关闭（×）。
inline QIcon closeIcon(const QColor &color)
{
    return detail::makeIcon([color](QPainter &painter, const QRectF &rect) {
        detail::beginIconFrame(&painter, rect);
        painter.setPen(detail::iconPen(color));
        painter.setBrush(Qt::NoBrush);
        painter.drawLine(QPointF(6.5, 6.5), QPointF(17.5, 17.5));
        painter.drawLine(QPointF(17.5, 6.5), QPointF(6.5, 17.5));
        painter.restore();
    });
}

inline QIcon closeIcon(const QPalette &palette)
{
    return closeIcon(palette.color(QPalette::Text));
}

// 记忆（堆叠卡片）。
inline QIcon memoryIcon(const QColor &color)
{
    return detail::makeIcon([color](QPainter &painter, const QRectF &rect) {
        detail::beginIconFrame(&painter, rect);
        painter.setBrush(Qt::NoBrush);
        painter.setPen(detail::iconPen(color, 1.7));
        painter.drawRoundedRect(QRectF(7.0, 4.0, 10.0, 4.2), 2.0, 2.0);
        painter.drawRoundedRect(QRectF(5.5, 9.0, 13.0, 4.2), 2.0, 2.0);
        painter.drawRoundedRect(QRectF(4.0, 14.0, 16.0, 4.2), 2.0, 2.0);
        painter.restore();
    });
}

inline QIcon memoryIcon(const QPalette &palette)
{
    return memoryIcon(palette.color(QPalette::Text));
}

// 同步（环形箭头）。
inline QIcon syncIcon(const QColor &color)
{
    return detail::makeIcon([color](QPainter &painter, const QRectF &rect) {
        detail::beginIconFrame(&painter, rect);
        painter.setBrush(Qt::NoBrush);
        painter.setPen(detail::iconPen(color));
        painter.drawEllipse(QPointF(12.0, 12.0), 5.4, 5.4);
        QPolygonF head;
        head << QPointF(12.0, 5.0) << QPointF(9.4, 8.2) << QPointF(14.6, 8.2);
        painter.setPen(Qt::NoPen);
        painter.setBrush(color);
        painter.drawPolygon(head);
        painter.restore();
    });
}

inline QIcon syncIcon(const QPalette &palette)
{
    return syncIcon(palette.color(QPalette::Text));
}

// 录入（托盘 + 向下箭头）。
inline QIcon importIcon(const QColor &color)
{
    return detail::makeIcon([color](QPainter &painter, const QRectF &rect) {
        detail::beginIconFrame(&painter, rect);
        painter.setBrush(Qt::NoBrush);
        painter.setPen(detail::iconPen(color));
        painter.drawRoundedRect(QRectF(5.0, 13.5, 14.0, 4.5), 2.0, 2.0);
        painter.drawLine(QPointF(12.0, 4.5), QPointF(12.0, 12.5));
        painter.drawLine(QPointF(12.0, 12.5), QPointF(9.0, 10.2));
        painter.drawLine(QPointF(12.0, 12.5), QPointF(15.0, 10.2));
        painter.restore();
    });
}

inline QIcon importIcon(const QPalette &palette)
{
    return importIcon(palette.color(QPalette::Text));
}

// 气泡（建议卡片弱图标）。
inline QIcon chatIcon(const QColor &color)
{
    return detail::makeIcon([color](QPainter &painter, const QRectF &rect) {
        detail::beginIconFrame(&painter, rect);
        QPainterPath bubble;
        bubble.addRoundedRect(QRectF(4.0, 4.5, 16.0, 11.5), 5.0, 5.0);
        QPolygonF tail;
        tail << QPointF(7.0, 16.0) << QPointF(4.5, 20.5) << QPointF(11.0, 16.0);
        bubble.addPolygon(tail);
        painter.setBrush(Qt::NoBrush);
        painter.setPen(detail::iconPen(color, 1.7));
        painter.drawPath(bubble);
        painter.restore();
    });
}

inline QIcon chatIcon(const QPalette &palette)
{
    return chatIcon(palette.color(QPalette::Text));
}

} // namespace ui

#endif // PIXIU_UI_ICONS_H
