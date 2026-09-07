#include "utils/thememanager.h"
#include <QApplication>
#include <QDebug>
#include <QLabel>
#include <QLineEdit>
#include <QTabWidget>
#include <QVBoxLayout>

int main(int argc, char **argv)
{
    QApplication app(argc, argv);
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
    content->addStretch();
    tabs->addTab(page, QStringLiteral("Memory"));
    layout->addWidget(tabs);
    host.resize(500, 400);
    auto &theme = ThemeManager::instance();
    theme.applySavedTheme(&app);
    host.show();
    for (auto mode : {ThemeManager::Light, ThemeManager::Dark, ThemeManager::Light}) {
        theme.setThemeMode(mode);
        QApplication::processEvents();
        const QColor expected(mode == ThemeManager::Dark ? "#101418" : "#f6f7f9");
        const auto pixels = page->grab().toImage();
        const auto actual = pixels.pixelColor(page->width() / 2, page->height() - 15);
        if (actual != expected) {
            qCritical() << "Workspace background disagrees with active theme:" << actual << expected;
            return 1;
        }
        const QColor surface(mode == ThemeManager::Dark ? "#171c22" : "#ffffff");
        if (input->grab().toImage().pixelColor(input->width()/2, input->height()/2) != surface) {
            qCritical() << "Input surface lost its distinct theme background";
            return 1;
        }
    }
    qInfo() << "Rendered host theme backgrounds: PASS";
}
