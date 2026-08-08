#include "app/AppSettings.h"

#include <QLoggingCategory>
#include <QSettings>

Q_LOGGING_CATEGORY(lcSettings, "pixiu.settings")

AppSettings::AppSettings(QObject *parent)
    : QObject(parent)
    , m_settings(new QSettings(this))
{
    qCInfo(lcSettings) << "settings file:" << m_settings->fileName();
}

AppSettings::~AppSettings() = default;

bool AppSettings::contains(const QString &key) const
{
    return m_settings->contains(key);
}

QVariant AppSettings::value(const QString &key, const QVariant &defaultValue) const
{
    return m_settings->value(key, defaultValue);
}

void AppSettings::setValue(const QString &key, const QVariant &value)
{
    m_settings->setValue(key, value);
}

void AppSettings::sync()
{
    m_settings->sync();
}

QString AppSettings::fileName() const
{
    return m_settings->fileName();
}
