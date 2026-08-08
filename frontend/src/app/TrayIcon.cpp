#include "app/TrayIcon.h"

#include <QApplication>
#include <QIcon>
#include <QLoggingCategory>
#include <QMenu>
#include <QPainter>
#include <QPixmap>
#include <QSystemTrayIcon>

Q_LOGGING_CATEGORY(lcTray, "pixiu.tray")

namespace {
// 生成一个占位图标（后续 feature 替换为资源图标）：蓝底圆角方块 + 白点。
QIcon createPlaceholderIcon()
{
    QPixmap pixmap(64, 64);
    pixmap.fill(Qt::transparent);

    QPainter painter(&pixmap);
    painter.setRenderHint(QPainter::Antialiasing);
    painter.setBrush(QColor(0x35, 0x87, 0xF6));
    painter.setPen(Qt::NoPen);
    painter.drawRoundedRect(2, 2, 60, 60, 14, 14);
    painter.setBrush(Qt::white);
    painter.drawEllipse(22, 22, 20, 20);
    painter.end();
    return QIcon(pixmap);
}
}

TrayIcon::TrayIcon(QObject *parent)
    : QObject(parent)
{
}

bool TrayIcon::show()
{
    if (!QSystemTrayIcon::isSystemTrayAvailable()) {
        qCInfo(lcTray) << "system tray is not available; tray integration disabled";
        return false;
    }

    m_tray = new QSystemTrayIcon(createPlaceholderIcon(), this);
    m_tray->setToolTip(tr("PIXIU 貔貅"));
    buildMenu();
    m_tray->show();
    qCInfo(lcTray) << "tray icon shown";
    return true;
}

void TrayIcon::hide()
{
    if (m_tray) {
        m_tray->hide();
        m_tray->deleteLater();
        m_tray = nullptr;
    }
}

QSystemTrayIcon *TrayIcon::trayIcon() const
{
    return m_tray;
}

void TrayIcon::buildMenu()
{
    QMenu *menu = new QMenu();

    QAction *openAction = menu->addAction(tr("打开 PIXIU"));
    QAction *quitAction = menu->addAction(tr("退出"));

    connect(openAction, &QAction::triggered, this, &TrayIcon::openRequested);
    connect(quitAction, &QAction::triggered, this, &TrayIcon::quitRequested);

    m_tray->setContextMenu(menu);
}
