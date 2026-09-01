#ifndef PIXIU_UPGRADE_CONTROLLER_H
#define PIXIU_UPGRADE_CONTROLLER_H

#include <QObject>
#include <QString>
#include <QStringList>
#include <QUrl>

#include <functional>

#include "app/UpgradeUtils.h"

class QNetworkAccessManager;
class QNetworkReply;
class QProcess;
class QSaveFile;

// 应用内一键升级控制器：检查/下载/校验/安装状态机（仿 SyncController /
// DeliveryController，但网络走 GitHub 直连，不经 backend transport）。
//
// 流程：checkForUpdate → (Checking) → Updatable | UpToDate | Failed；
//       仅 Updatable 可 downloadAndInstall → Downloading → Verifying →
//       Installing → Success | Failed | Cancelled。
// 安全铁律：HTTPS + sha256 双校验（ui::verifySha256），安装经 pkexec（polkit
//       认证框），不绕过授权；失败/取消清理临时 deb，不自动重启（手动提示）。
//
// 测试 seam：
//   - 网络：默认用内部 QNetworkAccessManager 直连 GitHub；测试可通过注入
//     release-latest 的 QUrl（指向本地 QTcpServer 假 HTTP）走真实网络栈，
//     ReleaseInfo 的 debUrl/shaUrl 由响应 JSON 也指到同一本地 server。
//   - 安装：默认 QProcess::start("pkexec", {"dpkg","-i",deb})；测试可注入
//     installRunner,发 argv + onFinished(exitCode)，避免真实 pkexec/polkit。
class UpgradeController : public QObject
{
    Q_OBJECT

public:
    // 升级状态机。Idle：初始/复位；Checking：检测；Updatable：发现新版本；
    // UpToDate：已是最新；Downloading：下载 deb；Verifying：sha256 校验；
    // Installing：pkexec dpkg 安装；Success/Cancelled/Failed：终态。
    enum class State {
        Idle,
        Checking,
        Updatable,
        UpToDate,
        Downloading,
        Verifying,
        Installing,
        Success,
        Cancelled,
        Failed,
    };

    // 安装执行器：接收 program（"pkexec"）、argv（["dpkg","-i",debPath]）与
    // 完成后回调退出码。默认实现用 pkexec 启动；测试注入替身记录并自行回调。
    using InstallRunner = std::function<void(
        const QString &program, const QStringList &args,
        const std::function<void(int)> &onFinished)>;

    // 下载源可信判定：默认要求 https + GitHub host allowlist（防篡改的 release
    // 元数据把 deb/sha URL 指向任意 http:// host 造成 MITM）。测试注入宽松判定
    // 覆盖本地假 server 的 http://127.0.0.1 下载 URL。
    using SourceValidator = std::function<bool(const QUrl &)>;

    explicit UpgradeController(QObject *parent = nullptr);

    // 测试 seam：注入网络管理器与 release-latest URL（指向本地假 server）。
    UpgradeController(QNetworkAccessManager *network, const QUrl &releaseUrl,
                      QObject *parent = nullptr);

    ~UpgradeController() override;

    State state() const { return m_state; }

    // 检测新版本：State->Checking；GET release/latest → parseRelease →
    // compareVersions(remote, applicationVersion)。>0 → Updatable +
    // remoteVersionFound；否则 UpToDate；失败 → Failed + upgradeFinished(false,
    // tr("无法连接更新服务器"))。
    void checkForUpdate();

    // 下载 + 校验 + 安装（仅 Updatable 可调）。下载流式写入 TempLocation
    // 的 pixiu-update.deb，进度 progressChanged(0-100)；随后 GET sha256 →
    // ui::verifySha256；通过才 Installing，不通过清理 + Failed。
    void downloadAndInstall();

    // 取消下载/校验/安装：清理临时 deb + 停止进行中的 reply/process →
    // State->Cancelled + upgradeFinished(false, tr("已取消"))。
    void cancel();

    // 测试 seam：注入安装执行器（替换默认 QProcess pkexec 路径）。
    void setInstallRunner(InstallRunner runner);

    // 测试 seam：覆盖「下载源可信」判定（默认 https + GitHub host allowlist）。
    void setSourceValidator(SourceValidator validator)
    {
        m_sourceValidator = std::move(validator);
    }

signals:
    void stateChanged(State state);
    // parseRelease 后 normalizeVersion 的纯版本号（如 "0.1.6"）。
    void remoteVersionFound(const QString &version);
    // 下载进度 0-100。
    void progressChanged(int percent);
    // 流程结束：check 完成 / 下载校验安装完成 / 失败 / 取消。
    void upgradeFinished(bool success, const QString &message);

private:
    void setState(State state);
    void resetTransport(); // 清理在途 reply/file/process + 临时 deb
    void handleCheckFinished();
    void handleDownloadFinished();
    void fetchSha();
    void handleShaFinished(QNetworkReply *reply);
    void startInstall();
    void handleInstallFinished(int exitCode);

    QNetworkAccessManager *m_network = nullptr;
    QUrl m_releaseUrl;
    ui::ReleaseInfo m_release;
    State m_state = State::Idle;
    QString m_debPath;

    QNetworkReply *m_checkReply = nullptr;
    QNetworkReply *m_downloadReply = nullptr;
    QNetworkReply *m_shaReply = nullptr;
    QSaveFile *m_downloadFile = nullptr;
    QProcess *m_installProcess = nullptr;
    InstallRunner m_installRunner;
    SourceValidator m_sourceValidator;
};

// 使 State 可用于 QVariant（QSignalSpy 记录 / 信号跨线程排队依赖）。
Q_DECLARE_METATYPE(UpgradeController::State)

#endif // PIXIU_UPGRADE_CONTROLLER_H
