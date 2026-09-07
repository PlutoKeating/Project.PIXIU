#include "utils/thememanager.h"
#include <QApplication>
#include <QCalendarWidget>
#include <QDebug>
#include <QDateEdit>
#include <QLabel>
#include <QLineEdit>
#include <QListWidget>
#include <QPainter>
#include <QProxyStyle>
#include <QStyleOption>
#include <QTabBar>
#include <QTabWidget>
#include <QToolButton>
#include <QVBoxLayout>

// Model the native style painting dark active controls despite a light palette.
// A stylesheet must own both foreground and surface for these controls.
class ConflictingControlStyle : public QProxyStyle {
public:
    void drawControl(ControlElement element, const QStyleOption *option,
                     QPainter *painter, const QWidget *widget = nullptr) const override
    {
        if (element == CE_ItemViewItem && (option->state & State_Selected)) {
            painter->fillRect(option->rect, QColor("#cccccc"));
            painter->setPen(Qt::white);
            painter->drawText(option->rect, QStringLiteral("Memory source"));
            return;
        }
        if (element == CE_TabBarTabShape && (option->state & State_Selected)) {
            painter->fillRect(option->rect, QColor("#1e1e1e"));
            return;
        }
        QProxyStyle::drawControl(element, option, painter, widget);
    }
    void drawComplexControl(ComplexControl control, const QStyleOptionComplex *option,
                            QPainter *painter, const QWidget *widget = nullptr) const override
    {
        if (control == CC_SpinBox && (option->state & State_HasFocus)) {
            painter->fillRect(option->rect, QColor("#1e1e1e"));
            return;
        }
        QProxyStyle::drawComplexControl(control, option, painter, widget);
    }
};

int main(int argc, char **argv)
{
    QApplication app(argc, argv);
    app.setStyle(new ConflictingControlStyle);
    app.setOrganizationName(QStringLiteral("PIXIU-Test"));
    app.setApplicationName(QStringLiteral("host-theme-regression"));
    QWidget host;
    auto *layout = new QVBoxLayout(&host);
    auto *tabs = new QTabWidget(&host);
    auto *page = new QWidget(tabs);
    page->setAutoFillBackground(true);
    QPalette conflicting = page->palette();
    conflicting.setColor(QPalette::Window, QColor("#1f1f1f"));
    page->setPalette(conflicting);
    auto *content = new QVBoxLayout(page);
    content->addWidget(new QLabel(QStringLiteral("Readable workspace"), page));
    auto *input = new QLineEdit(page);
    content->addWidget(input);
    auto *sources = new QListWidget(page);
    sources->setObjectName(QStringLiteral("memorySources"));
    sources->setFixedHeight(64);
    sources->addItem(QStringLiteral("Memory source"));
    sources->setCurrentRow(0);
    content->addWidget(sources);
    auto *date = new QDateEdit(QDate(2026, 9, 7), page);
    date->setCalendarPopup(true);
    content->addWidget(date);
    auto *month = date->calendarWidget()->findChild<QToolButton *>(QStringLiteral("qt_calendar_monthbutton"));
    if (!month) {
        qCritical() << "Calendar navigation button missing";
        return 1;
    }
    QPalette conflictingCalendar = month->palette();
    conflictingCalendar.setColor(QPalette::ButtonText, Qt::white);
    month->setPalette(conflictingCalendar);
    content->addStretch();
    tabs->addTab(page, QStringLiteral("Memory"));
    layout->addWidget(tabs);
    host.resize(500, 400);
    auto &theme = ThemeManager::instance();
    theme.applySavedTheme(&app);
    host.show();
    int failures = 0;
    for (auto mode : {ThemeManager::Light, ThemeManager::Dark, ThemeManager::Light}) {
        theme.setThemeMode(mode);
        QApplication::processEvents();
        const QColor expected(mode == ThemeManager::Dark ? "#101418" : "#f6f7f9");
        const auto pixels = page->grab().toImage();
        const auto actual = pixels.pixelColor(page->width() / 2, page->height() - 15);
        if (actual != expected) {
            qCritical() << "Workspace background disagrees with active theme:" << actual << expected;
            ++failures;
        }
        const QColor surface(mode == ThemeManager::Dark ? "#171c22" : "#ffffff");
        if (input->grab().toImage().pixelColor(input->width()/2, input->height()/2) != surface) {
            qCritical() << "Input surface lost its distinct theme background";
            ++failures;
        }
        const QRect tab = tabs->tabBar()->tabRect(0);
        const QColor selection(mode == ThemeManager::Dark ? "#111d2c" : "#e6f4ff");
        if (tabs->tabBar()->grab().toImage().pixelColor(tab.right()-8, tab.center().y()) != selection) {
            qCritical() << "Selected tab surface disagrees with active theme";
            ++failures;
        }
        date->setFocus();
        QApplication::processEvents();
        if (date->grab().toImage().pixelColor(date->width()/2, date->height()/2) != surface) {
            qCritical() << "Focused date surface disagrees with active theme";
            ++failures;
        }
        date->calendarWidget()->show();
        QApplication::processEvents();
        const QColor text(mode == ThemeManager::Dark ? "#f3f6f8" : "#172033");
        date->calendarWidget()->hide();
        host.activateWindow();
        for (bool focused : {true, false}) {
            if (focused) sources->setFocus();
            else input->setFocus();
            QApplication::processEvents();
            if (sources->hasFocus() != focused) {
                qCritical() << "Source focus fixture did not reach requested state";
                ++failures;
            }
            const auto row = sources->visualItemRect(sources->item(0));
            const auto image = sources->viewport()->grab().toImage();
            bool hasText = false;
            for (int y = row.top(); y <= row.bottom(); ++y)
                for (int x = row.left(); x < row.center().x(); ++x)
                    hasText |= image.pixelColor(x, y) == text;
            if (image.pixelColor(row.right()-10, row.center().y()) != selection || !hasText) {
                qCritical() << "Selected source foreground/surface disagrees with theme" << focused
                            << image.pixelColor(row.right()-10, row.center().y()) << selection << hasText;
                ++failures;
            }
        }
        if (month->palette().color(QPalette::ButtonText) != text ||
            month->grab().toImage().pixelColor(3, month->height()/2) != surface) {
            qCritical() << "Calendar navigation foreground/surface disagrees with active theme";
            ++failures;
        }
        date->calendarWidget()->hide();
    }
    // Theme repaint is queued; a popup may disappear before it is delivered.
    auto *transient = new QWidget;
    transient->show();
    theme.setThemeMode(ThemeManager::Dark);
    delete transient;
    QApplication::processEvents();
    if (failures) return 1;
    qInfo() << "Rendered host theme backgrounds and active controls: PASS";
}
