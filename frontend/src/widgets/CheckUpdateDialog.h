#ifndef PIXIU_CHECK_UPDATE_DIALOG_H
#define PIXIU_CHECK_UPDATE_DIALOG_H

#include <QDialog>

#include "app/UpgradeController.h"

class QLabel;
class QProgressBar;
class QPushButton;

// 检查更新对话框：应用内一键升级（检查/下载/校验/安装）的用户掌控面。
//
// 注入的 UpgradeController 为共享状态机（PixiuApp 持有）；未注入时对话框
// 自建为空（不触发网络），升级按钮保持禁用——选择「不注入则禁用升级」。
//
// 状态到 UI（signal → 控件）：
//   stateChanged          → updateStatusLabel + 按钮 enabled/visible
//   remoteVersionFound    → remoteVersionLabel（远程最新版本）
//   progressChanged       → updateProgressBar（0-100，下载中显示）
//   upgradeFinished       → updateStatusLabel（成功提示手动重启；
//                           失败按 reason 分发，网络失败时远程行显示错误文案）
//
// UI 不自动重启：升级成功后仅提示「请手动重启应用以生效」，由用户自行重启。
class CheckUpdateDialog : public QDialog
{
    Q_OBJECT

public:
    explicit CheckUpdateDialog(UpgradeController *controller = nullptr,
                               QWidget *parent = nullptr);

    void showAndFocus();

    // 显示对话框并触发一次检查（controller 已注入时）。若 controller 为
    // nullptr 则仅显示（升级按钮禁用）。
    // 注意：不能命名为 open()——与基类 QDialog::open()（public slot）同签名，
    // 经 QDialog* 或 QMetaObject::invokeMethod 调用会落到基类模态行为而非
    // 本实现，须改名规避（showAndCheck）。
    void showAndCheck();

    // 注入的升级控制器（为 nullptr 表示未注入，升级按钮禁用）。
    UpgradeController *controller() const { return m_controller; }

public slots:
    void reject() override;

private:
    bool operationActive() const;
    void connectController();
    void onStateChanged(UpgradeController::State state);
    void onRemoteVersionFound(const QString &version);
    void onProgressChanged(int percent);
    void onUpgradeFinished(bool success, const QString &message,
                           UpgradeController::FailedReason reason);

    UpgradeController *m_controller = nullptr;
    QLabel *m_currentVersionLabel = nullptr;
    QLabel *m_remoteVersionLabel = nullptr;
    QLabel *m_updateStatusLabel = nullptr;
    QProgressBar *m_updateProgressBar = nullptr;
    QPushButton *m_checkAgainButton = nullptr;
    QPushButton *m_upgradeButton = nullptr;
    QPushButton *m_cancelButton = nullptr;
    QPushButton *m_closeButton = nullptr;
    // 最近一次发现/下载的版本与进度（供状态切换与文案回填）。
    QString m_remoteVersion;
    int m_progress = 0;
};

#endif // PIXIU_CHECK_UPDATE_DIALOG_H
