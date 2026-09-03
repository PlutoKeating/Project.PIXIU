#ifndef PIXIU_UPGRADE_CONTROLLER_H
#define PIXIU_UPGRADE_CONTROLLER_H

#include <QByteArray>
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
// 安全铁律：HTTPS + sha256 完整性校验；安装经 pkexec 调用 root-only helper，
//       再以固定 Ed25519 公钥验证独立签名，不绕过授权；失败/取消清理临时 deb，
//       不自动重启（手动提示）。
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

    // 失败类别（upgradeFinished 的 reason 参数；None 表示非失败路径）。
    // 供 UI 按原因分发，避免对本地化 message 做字符串比较（message 经
    // tr() 本地化，跨 tr() 上下文/语言比较会在非中文 locale 分化）。
    enum class FailedReason {
        None,          // 非失败路径（成功 / UpToDate / 取消按终态处理）
        Network,       // 无法连接更新服务器 / 网络 / HTTP / 超时错误
        Verify,        // 下载包校验未通过
        InvalidSource, // 更新源非可信下载源（http / 非 allowlist host）
        Download,      // 下载失败（网络 / 写入 / 提交失败）
        Install,       // pkexec/dpkg 启动或执行失败
        Health,        // dpkg 成功但新组件版本/schema/服务健康校验失败
        Other,         // 其它失败（本地文件 / 进程异常等）
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
    // remoteVersionFound；否则 UpToDate；失败 → Failed +
    // upgradeFinished(false, tr("无法连接更新服务器"), FailedReason::Network)。
    void checkForUpdate();

    // 下载 + 校验 + 安装（仅 Updatable 可调）。下载流式写入 TempLocation
    // 的 pixiu-update.deb，进度 progressChanged(0-100)；随后 GET sha256 与独立
    // 签名；摘要通过后由特权 helper 验签，任一缺失均不进入 dpkg。
    void downloadAndInstall();

    // 取消下载/校验：清理临时 deb + 停止进行中的 reply。安装开始后不允许
    // 强制取消，避免中断 dpkg 后留下半配置的软件包。
    void cancel();

    // 测试 seam：注入安装执行器（替换默认 QProcess pkexec 路径）。
    void setInstallRunner(InstallRunner runner);
    void setInstallProgramForTest(const QString &program)
    {
        m_installProgram = program;
    }

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
    // reason 区分失败类别（None 表示非失败路径），供 UI 按原因而非 message
    // 分发——message 经 tr() 本地化，跨上下文/语言做字符串比较不可靠。
    void upgradeFinished(bool success, const QString &message,
                         FailedReason reason);

private:
    void setState(State state);
    void resetTransport(); // 清理在途 reply/file/process + 临时 deb
    void handleCheckFinished();
    void handleDownloadFinished();
    void fetchSha();
    void handleShaFinished(QNetworkReply *reply);
    void fetchSignature();
    void handleSignatureFinished(QNetworkReply *reply);
    void startInstall();
    void handleInstallFinished(int exitCode);
    void protectRedirect(QNetworkReply *reply);
    void collectBoundedReply(QNetworkReply *reply, QByteArray &target,
                             qint64 maximumBytes);
    void failInstall(const QString &message);

    QNetworkAccessManager *m_network = nullptr;
    QUrl m_releaseUrl;
    ui::ReleaseInfo m_release;
    State m_state = State::Idle;
    QString m_debPath;
    QString m_expectedSha256;
    QString m_signatureBase64;

    QNetworkReply *m_checkReply = nullptr;
    QNetworkReply *m_downloadReply = nullptr;
    QNetworkReply *m_shaReply = nullptr;
    QNetworkReply *m_signatureReply = nullptr;
    QSaveFile *m_downloadFile = nullptr;
    QByteArray m_checkBody;
    QByteArray m_shaBody;
    QByteArray m_signatureBody;
    qint64 m_downloadBytes = 0;
    QProcess *m_installProcess = nullptr;
    QString m_installErrorOutput;
    InstallRunner m_installRunner;
    SourceValidator m_sourceValidator;
    QString m_installProgram = QStringLiteral("/usr/bin/pkexec");
};

// 使 State / FailedReason 可用于 QVariant（QSignalSpy 记录 / 信号跨线程排队依赖）。
Q_DECLARE_METATYPE(UpgradeController::State)
Q_DECLARE_METATYPE(UpgradeController::FailedReason)

#endif // PIXIU_UPGRADE_CONTROLLER_H
