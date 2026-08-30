#ifndef PIXIU_SETTINGS_DIALOG_H
#define PIXIU_SETTINGS_DIALOG_H

#include <QDialog>
#include <QKeySequence>
#include <QString>

class QComboBox;
class QKeySequenceEdit;
class QPushButton;

// 应用设置对话框：界面语言偏好 + 关于信息。
//
// 本控件只负责收集与展示选择，不直接读写 QSettings；语言偏好由应用层在
// accepted 后持久化（AppSettings::keyLanguage）并在下次启动时生效。
class SettingsDialog : public QDialog
{
    Q_OBJECT

public:
    explicit SettingsDialog(QWidget *parent = nullptr);

    void showAndFocus();

    // 当前选择的语言代码："system"（跟随系统）/ "zh_CN" / "en_US"。
    QString selectedLanguage() const;
    // 按已保存偏好初始化选择；未知/空值回退“跟随系统”。
    void setLanguage(const QString &language);

    // 当前选择的全局快捷键（默认 Ctrl+Alt+P）。
    QKeySequence selectedShortcut() const;
    // 按已保存偏好初始化快捷键；空值回退默认序列。
    void setShortcut(const QKeySequence &sequence);

signals:
    // 取消 / Esc / 窗口关闭。
    void cancelled();
    // “监控中心…”按钮：由应用层打开监控中心面板（懒创建）。
    void monitorCenterRequested();
    // 关于与法律四入口：由应用层懒创建并打开对应页面
    //（检查更新 / 关于 PIXIU / 服务条款 / 隐私政策）。
    void checkUpdateRequested();
    void aboutUsRequested();
    void termsRequested();
    void privacyRequested();

private:
    void updateOkEnabled();

    QComboBox *m_languageCombo = nullptr;
    QKeySequenceEdit *m_shortcutEdit = nullptr;
    QPushButton *m_okButton = nullptr;
    QPushButton *m_monitorButton = nullptr;
};

#endif // PIXIU_SETTINGS_DIALOG_H
