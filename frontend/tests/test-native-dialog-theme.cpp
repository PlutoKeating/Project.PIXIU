#include "utils/kylinfiledialog.h"
#include "utils/pixiu_desktop.h"
#include "utils/thememanager.h"
#include <QApplication>
#include <QDebug>
#include <QTimer>
#include <cmath>

static double luminance(const QColor &color)
{
    auto linear = [](double value) {
        return value <= .04045 ? value / 12.92 : std::pow((value + .055) / 1.055, 2.4);
    };
    return .2126 * linear(color.redF()) + .7152 * linear(color.greenF())
        + .0722 * linear(color.blueF());
}

int main(int argc, char **argv)
{
    QApplication app(argc, argv);
    app.setOrganizationName(QStringLiteral("PIXIU-Test"));
    app.setApplicationName(QStringLiteral("native-dialog-theme"));
    auto &theme = ThemeManager::instance();
    theme.applySavedTheme(&app);
    int failures = 0;
    for (auto mode : {ThemeManager::Light, ThemeManager::Dark, ThemeManager::Light}) {
        theme.setThemeMode(mode);
        bool inspected = false;
        QTimer::singleShot(300, &app, [&] {
            auto *window = qobject_cast<kdk::KDialog *>(QApplication::activeModalWidget());
            if (!window) {
                qCritical() << "The real file picker did not open its SDK dialog";
                ++failures;
                app.exit(1);
                return;
            }
            auto *close = window->closeButton();
            // Capture the composed window: the button alone may be transparent.
            const auto image = window->grab().toImage();
            const qreal scale = image.devicePixelRatio();
            const QPoint origin = close->mapTo(window, QPoint());
            const QPoint center = (origin + close->rect().center()) * scale;
            const QPoint sample = (origin + QPoint(2, close->height() / 2)) * scale;
            const double background = luminance(image.pixelColor(sample));
            const int radius = qRound(8 * scale);
            int visible = 0;
            double highest = 1;
            for (int y = center.y() - radius; y <= center.y() + radius; ++y) {
                for (int x = center.x() - radius; x <= center.x() + radius; ++x) {
                    const double pixel = luminance(image.pixelColor(x, y));
                    const double ratio = (qMax(pixel, background) + .05)
                        / (qMin(pixel, background) + .05);
                    highest = qMax(highest, ratio);
                    visible += ratio >= 3;
                }
            }
            qInfo() << "Native close control:" << mode << "contrast" << highest
                    << "visiblePixels" << visible;
            if (!close->isVisible() || !close->isEnabled() || visible < 12 * scale * scale)
                ++failures;
            inspected = true;
            close->click();
        });
        const QString selected = KylinFileDialog::getExistingDirectory(
            nullptr, QStringLiteral("PIXIU 原生关闭控件回归"), QStringLiteral("/var/tmp"));
        if (!inspected || !selected.isEmpty()) {
            qCritical() << "Closing the real picker must cancel without selecting a directory";
            ++failures;
        }
    }
    return failures ? 1 : 0;
}
