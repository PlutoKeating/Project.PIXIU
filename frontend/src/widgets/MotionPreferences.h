#pragma once
#include <QApplication>
#include <QSettings>

namespace pixiu {
// One persistent application policy for all product motion. New effects must
// observe this property and settle immediately when it changes.
class MotionPreferences {
public:
    static constexpr const char *propertyName = "pixiuInterfaceAnimations";
    static bool enabled()
    {
        if (!qApp->property(propertyName).isValid()) {
            const bool value = QSettings().value("appearance/animations", true).toBool();
            qApp->setProperty(propertyName, value);
            QApplication::setEffectEnabled(Qt::UI_General, value);
        }
        return qApp->property(propertyName).toBool();
    }
    static void setEnabled(bool value)
    {
        QSettings settings;
        settings.setValue("appearance/animations", value);
        settings.sync();
        QApplication::setEffectEnabled(Qt::UI_General, value);
        qApp->setProperty(propertyName, value);
    }
};
}
