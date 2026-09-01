#include "app/UpgradeController.h"

#include <QCoreApplication>
#include <QFile>
#include <QLoggingCategory>
#include <QNetworkAccessManager>
#include <QNetworkReply>
#include <QNetworkRequest>
#include <QProcess>
#include <QSaveFile>
#include <QStandardPaths>

Q_LOGGING_CATEGORY(lcUpgrade, "pixiu.upgrade")

namespace {
// 检查/下载/校验三请求的传输超时（ms）。Qt 5.15 默认 transferTimeout=0 禁用：
// 黑洞 server 会让状态机永远挂起。仿 HttpBackendTransport::kTransferTimeoutMs
// 先例（10000ms），升级传输取 15s（deb 较大）。
constexpr int kUpgradeTransferTimeoutMs = 15000;

// GitHub 资产下载源的铁律校验：HTTPS + host allowlist。GitHub 的
// browser_download_url 初始指向 github.com，302 后跳到
// objects.githubusercontent.com；release/latest API 亦在 api.github.com。
// 恶意/被篡改的 release 元数据若把 deb/sha 指向任意 http:// host 即在此拦截。
bool isGitHubDownloadSource(const QUrl &url)
{
    if (url.scheme() != QLatin1String("https")) {
        return false;
    }
    const QString host = url.host().toLower();
    return host == QLatin1String("github.com") || //
        host == QLatin1String("objects.githubusercontent.com") || //
        host == QLatin1String("api.github.com");
}
} // namespace

UpgradeController::UpgradeController(QObject *parent)
    : QObject(parent)
    , m_releaseUrl(QStringLiteral(
          "https://api.github.com/repos/PlutoKeating/Project.PIXIU/releases/latest"))
{
    m_network = new QNetworkAccessManager(this);
    m_sourceValidator = [](const QUrl &u) { return isGitHubDownloadSource(u); };
    qRegisterMetaType<UpgradeController::State>("UpgradeController::State");
}

UpgradeController::UpgradeController(QNetworkAccessManager *network,
                                     const QUrl &releaseUrl, QObject *parent)
    : QObject(parent)
    , m_network(network)
    , m_releaseUrl(releaseUrl)
{
    m_sourceValidator = [](const QUrl &u) { return isGitHubDownloadSource(u); };
    qRegisterMetaType<UpgradeController::State>("UpgradeController::State");
}

UpgradeController::~UpgradeController()
{
    // 中止在途请求 / 进程并清理临时 deb（test seam 下无 pkexec，安全）。
    resetTransport();
}

void UpgradeController::setInstallRunner(InstallRunner runner)
{
    m_installRunner = std::move(runner);
}

void UpgradeController::setState(State state)
{
    if (m_state == state) {
        return;
    }
    m_state = state;
    emit stateChanged(m_state);
}

// 清理在途对象与临时 deb：先 disconnect 再 abort/kill，避免迟到回调在
// 状态变迁后错误地再次推进状态机（cancel/destructor 语义下的安全中止）。
void UpgradeController::resetTransport()
{
    if (m_checkReply) {
        m_checkReply->disconnect(this);
        m_checkReply->abort();
        m_checkReply->deleteLater();
        m_checkReply = nullptr;
    }
    if (m_downloadReply) {
        m_downloadReply->disconnect(this);
        m_downloadReply->abort();
        m_downloadReply->deleteLater();
        m_downloadReply = nullptr;
    }
    if (m_shaReply) {
        m_shaReply->disconnect(this);
        m_shaReply->abort();
        m_shaReply->deleteLater();
        m_shaReply = nullptr;
    }
    if (m_downloadFile) {
        m_downloadFile->cancelWriting();
        delete m_downloadFile;
        m_downloadFile = nullptr;
    }
    if (m_installProcess) {
        m_installProcess->disconnect(this);
        m_installProcess->kill();
        m_installProcess->waitForFinished(1000);
        m_installProcess->deleteLater();
        m_installProcess = nullptr;
    }
    if (!m_debPath.isEmpty()) {
        QFile::remove(m_debPath);
        m_debPath.clear();
    }
}

void UpgradeController::checkForUpdate()
{
    switch (m_state) {
    case State::Checking:
    case State::Downloading:
    case State::Verifying:
    case State::Installing:
        return; // 在途流程未结束，忽略重入
    default:
        break;
    }
    resetTransport();
    setState(State::Checking);

    QNetworkRequest request(m_releaseUrl);
    request.setRawHeader("User-Agent", QByteArrayLiteral("Pixiu-Update/1.0"));
    // Qt 5.15 默认 ManualRedirectPolicy（不跟随）。GitHub release/latest 走
    // api.github.com，无需 302；仍统一跟随以防御中间层重定向（https→https）。
    request.setAttribute(QNetworkRequest::RedirectPolicyAttribute,
                         QNetworkRequest::NoLessSafeRedirectPolicy);
    request.setTransferTimeout(kUpgradeTransferTimeoutMs);
    m_checkReply = m_network->get(request);
    connect(m_checkReply, &QNetworkReply::finished, this,
            &UpgradeController::handleCheckFinished);
}

void UpgradeController::handleCheckFinished()
{
    QNetworkReply *reply = m_checkReply;
    m_checkReply = nullptr;
    if (!reply) {
        return;
    }
    if (m_state != State::Checking) {
        reply->deleteLater();
        return; // 已取消/复位，忽略迟到回调
    }
    const bool ok = reply->error() == QNetworkReply::NoError;
    const QByteArray body = reply->readAll();
    reply->deleteLater();

    if (!ok) {
        // 传输超时（setTransferTimeout → OperationCanceledError）与网络/HTTP
        // 失败同归「无法连接」路径（非 NoError 即判定失败）。
        qCWarning(lcUpgrade) << "check failed (network/http):" << m_releaseUrl;
        setState(State::Failed);
        emit upgradeFinished(false, tr("无法连接更新服务器"));
        return;
    }

    ui::ReleaseInfo info;
    if (!ui::parseRelease(body, info)) {
        qCWarning(lcUpgrade) << "release/latest parse failed";
        setState(State::Failed);
        emit upgradeFinished(false, tr("无法连接更新服务器"));
        return;
    }
    m_release = info;

    // parseRelease 已 normalizeVersion tag；再 normalize 一次幂等无害。
    const int cmp = ui::compareVersions(
        ui::normalizeVersion(m_release.tag),
        QCoreApplication::applicationVersion());
    if (cmp > 0) {
        setState(State::Updatable);
        emit remoteVersionFound(m_release.tag);
    } else {
        setState(State::UpToDate);
        emit upgradeFinished(true, tr("已是最新版本"));
    }
}

void UpgradeController::downloadAndInstall()
{
    if (m_state != State::Updatable || m_release.debUrl.isEmpty()) {
        return; // 仅 Updatable 且需含有效 deb 下载地址
    }
    // 安全铁律（HTTPS + GitHub host allowlist）：deb 与 sha 均为可信下载源才
    // 允许发起下载；否则 Failed + 更新源无效（不发起下载，不落盘）。
    const QUrl debUrl(m_release.debUrl);
    const QUrl shaUrl(m_release.shaUrl);
    if (!m_sourceValidator(debUrl) || !m_sourceValidator(shaUrl)) {
        qCWarning(lcUpgrade) << "untrusted download source:"
                             << m_release.debUrl << m_release.shaUrl;
        setState(State::Failed);
        emit upgradeFinished(false, tr("更新源无效"));
        return;
    }
    resetTransport();
    setState(State::Downloading);

    m_debPath = QStandardPaths::writableLocation(QStandardPaths::TempLocation)
        + QStringLiteral("/pixiu-update.deb");
    m_downloadFile = new QSaveFile(m_debPath);
    if (!m_downloadFile->open(QIODevice::WriteOnly)) {
        delete m_downloadFile;
        m_downloadFile = nullptr;
        QFile::remove(m_debPath);
        setState(State::Failed);
        emit upgradeFinished(false, tr("下载失败"));
        return;
    }

    QNetworkRequest request(debUrl);
    request.setRawHeader("User-Agent", QByteArrayLiteral("Pixiu-Update/1.0"));
    // Qt 5.15 默认 ManualRedirectPolicy（不跟随）：GitHub browser_download_url
    // 302 → objects.githubusercontent.com，manual 下 reply 以 302 + 空 body
    // 终止（error==NoError）→ 空文件 commit → verifySha256 失败 → 永远「校验
    // 失败」。须跟随 https→https、同 host / github.com→objects.githubusercontent
    // .com 的安全重定向。
    request.setAttribute(QNetworkRequest::RedirectPolicyAttribute,
                         QNetworkRequest::NoLessSafeRedirectPolicy);
    request.setTransferTimeout(kUpgradeTransferTimeoutMs);
    m_downloadReply = m_network->get(request);
    connect(m_downloadReply, &QNetworkReply::readyRead, this, [this]() {
        if (m_downloadFile && m_downloadReply) {
            m_downloadFile->write(m_downloadReply->readAll());
        }
    });
    connect(m_downloadReply, &QNetworkReply::downloadProgress, this,
            [this](qint64 received, qint64 total) {
                if (total > 0) {
                    emit progressChanged(
                        qBound(0, int(received * 100 / total), 100));
                }
            });
    connect(m_downloadReply, &QNetworkReply::finished, this,
            &UpgradeController::handleDownloadFinished);
}

void UpgradeController::handleDownloadFinished()
{
    QNetworkReply *reply = m_downloadReply;
    m_downloadReply = nullptr;
    if (!reply) {
        return;
    }
    if (m_state != State::Downloading) {
        reply->deleteLater();
        return; // 已取消/失败，忽略迟到回调
    }
    if (m_downloadFile) {
        m_downloadFile->write(reply->readAll()); // 排空剩余数据
    }
    const bool ok = reply->error() == QNetworkReply::NoError;
    reply->deleteLater();

    // 传输超时（setTransferTimeout → OperationCanceledError）与网络/HTTP 失败
    // 同归「下载失败」路径（非 NoError 即判定失败）。
    if (!ok || !m_downloadFile || !m_downloadFile->commit()) {
        if (m_downloadFile) {
            m_downloadFile->cancelWriting();
            delete m_downloadFile;
            m_downloadFile = nullptr;
        }
        QFile::remove(m_debPath);
        m_debPath.clear();
        setState(State::Failed);
        emit upgradeFinished(false, tr("下载失败"));
        return;
    }
    delete m_downloadFile;
    m_downloadFile = nullptr;
    emit progressChanged(100);
    setState(State::Verifying);
    fetchSha();
}

void UpgradeController::fetchSha()
{
    QNetworkRequest request(QUrl(m_release.shaUrl));
    request.setRawHeader("User-Agent", QByteArrayLiteral("Pixiu-Update/1.0"));
    // 同 deb：GitHub .deb.sha256 browser_download_url 亦会 302 →
    // objects.githubusercontent.com，须跟随；并设传输超时。
    request.setAttribute(QNetworkRequest::RedirectPolicyAttribute,
                         QNetworkRequest::NoLessSafeRedirectPolicy);
    request.setTransferTimeout(kUpgradeTransferTimeoutMs);
    m_shaReply = m_network->get(request);
    QNetworkReply *sha = m_shaReply;
    connect(sha, &QNetworkReply::finished, this,
            [this, sha]() { handleShaFinished(sha); });
}

void UpgradeController::handleShaFinished(QNetworkReply *reply)
{
    if (m_shaReply == reply) {
        m_shaReply = nullptr;
    }
    if (!reply) {
        return;
    }
    const bool ok = reply->error() == QNetworkReply::NoError;
    const QByteArray body = reply->readAll();
    reply->deleteLater();

    if (m_state != State::Verifying) {
        return; // 已取消/失败，忽略迟到回调
    }
    // sha 获取失败（网络错误 / 传输超时 → OperationCanceledError）：并入
    // 「下载失败」路径，与校验不通过区分，避免把网络问题误报为「校验失败」。
    if (!ok) {
        QFile::remove(m_debPath);
        m_debPath.clear();
        setState(State::Failed);
        emit upgradeFinished(false, tr("下载失败"));
        return;
    }
    const QString expected = QString::fromLatin1(body);
    if (!ui::verifySha256(m_debPath, expected)) {
        QFile::remove(m_debPath);
        m_debPath.clear();
        setState(State::Failed);
        emit upgradeFinished(false, tr("校验失败，已中止"));
        return;
    }
    startInstall();
}

void UpgradeController::startInstall()
{
    setState(State::Installing);

    const QStringList args{QStringLiteral("dpkg"), QStringLiteral("-i"),
                           m_debPath};
    if (m_installRunner) {
        // test seam：注入的执行器记录 program/argv 并自行回调退出码。
        m_installRunner(QStringLiteral("pkexec"), args, [this](int exitCode) {
            handleInstallFinished(exitCode);
        });
        return;
    }

    m_installProcess = new QProcess(this);
    connect(m_installProcess,
            QOverload<int, QProcess::ExitStatus>::of(&QProcess::finished),
            this, [this](int exitCode, QProcess::ExitStatus) {
                handleInstallFinished(exitCode);
            });
    m_installProcess->setProgram(QStringLiteral("pkexec"));
    m_installProcess->setArguments(args);
    m_installProcess->start();
}

void UpgradeController::handleInstallFinished(int exitCode)
{
    if (m_state != State::Installing) {
        return; // 已取消，忽略迟到的进程退出回调
    }
    if (m_installProcess) {
        m_installProcess->deleteLater();
        m_installProcess = nullptr;
    }
    if (!m_debPath.isEmpty()) {
        QFile::remove(m_debPath);
        m_debPath.clear();
    }
    if (exitCode == 0) {
        setState(State::Success);
        emit upgradeFinished(true, tr("升级成功，请手动重启应用以生效"));
    } else if (exitCode == 126 || exitCode == 127) {
        setState(State::Cancelled);
        emit upgradeFinished(false, tr("已取消，升级未执行"));
    } else {
        setState(State::Failed);
        emit upgradeFinished(false, tr("升级失败，请检查系统日志"));
    }
}

void UpgradeController::cancel()
{
    switch (m_state) {
    case State::Downloading:
    case State::Verifying:
    case State::Installing:
        break;
    default:
        return; // 仅下载/校验/安装中可取消
    }
    setState(State::Cancelled);
    resetTransport();
    emit upgradeFinished(false, tr("已取消"));
}
