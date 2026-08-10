#ifndef PIXIU_APP_SETTINGS_H
#define PIXIU_APP_SETTINGS_H

#include <QObject>
#include <QString>
#include <QVariant>

class QSettings;

// 应用级设置持久化（基于 QSettings）。
//
// 本阶段仅提供基础读写能力与应用级键名，窗口/业务配置在各自 feature 中
// 通过 instance() 追加使用，避免在 Widget 内直接操作 QSettings。
class AppSettings : public QObject
{
    Q_OBJECT

public:
    // 应用级设置键（统一在此声明，便于审查与迁移）。
    static inline const QString keyLastLaunched = QStringLiteral("app/meta/last_launched_ts");
    static inline const QString keyLanguage = QStringLiteral("app/general/language");
    static inline const QString keyTheme = QStringLiteral("app/general/theme");
    static inline const QString keyToggleShortcut = QStringLiteral("app/shortcut/toggle");
    static inline const QString keyWindowGeometry = QStringLiteral("app/window/geometry");
    static inline const QString keyBallPosition = QStringLiteral("app/floating_ball/position");

    explicit AppSettings(QObject *parent = nullptr);
    ~AppSettings() override;

    bool contains(const QString &key) const;
    QVariant value(const QString &key, const QVariant &defaultValue = QVariant()) const;
    void setValue(const QString &key, const QVariant &value);
    void sync();

    // 底层配置文件路径（用于诊断）。
    QString fileName() const;

private:
    QSettings *m_settings = nullptr;
};

#endif // PIXIU_APP_SETTINGS_H
