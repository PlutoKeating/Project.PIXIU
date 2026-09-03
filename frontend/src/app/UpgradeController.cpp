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
#include <QTemporaryFile>

Q_LOGGING_CATEGORY(lcUpgrade, "pixiu.upgrade")

namespace {
// 检查/下载/校验三请求的传输超时（ms）。Qt 5.15 默认 transferTimeout=0 禁用：
// 黑洞 server 会让状态机永远挂起。仿 HttpBackendTransport::kTransferTimeoutMs
// 先例（10000ms），升级传输取 15s（deb 较大）。
constexpr int kUpgradeTransferTimeoutMs = 15000;
constexpr qint64 kMaxReleaseMetadataBytes = 1024 * 1024;
constexpr qint64 kMaxChecksumBytes = 64 * 1024;
constexpr qint64 kMaxPackageBytes = 512LL * 1024 * 1024;

// GitHub 资产下载源的铁律校验：HTTPS + host allowlist。GitHub 的
// browser_download_url 初始指向 github.com，302 后跳到
// objects.githubusercontent.com / release-assets.githubusercontent.com；
// release/latest API 亦在 api.github.com。
// 恶意/被篡改的 release 元数据若把 deb/sha 指向任意 http:// host 即在此拦截。
bool isGitHubDownloadSource(const QUrl &url)
{
    if (url.scheme() != QLatin1String("https")) {
        return false;
    }
    const QString host = url.host().toLower();
    return host == QLatin1String("github.com") || //
        host == QLatin1String("objects.githubusercontent.com") || //
        host == QLatin1String("release-assets.githubusercontent.com") || //
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
    // 中止网络请求；已进入系统安装的进程必须继续，避免中断 dpkg。
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
    bool preserveDebForInstaller = false;
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
        if (m_state == State::Installing
            && m_installProcess->state() != QProcess::NotRunning) {
            // 应用退出也不能杀死正在写包数据库的 dpkg。解除 QObject 所有权，
            // 让已启动的系统安装进程自行完成，并保留其仍可能读取的 deb。
            preserveDebForInstaller = true;
            m_installProcess->setParent(nullptr);
        } else {
            m_installProcess->kill();
            m_installProcess->waitForFinished(1000);
            m_installProcess->deleteLater();
        }
        m_installProcess = nullptr;
    }
    if (!m_debPath.isEmpty() && !preserveDebForInstaller) {
        QFile::remove(m_debPath);
        m_debPath.clear();
    }
    m_checkBody.clear();
    m_shaBody.clear();
    m_downloadBytes = 0;
    m_expectedSha256.clear();
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
    protectRedirect(m_checkReply);
    connect(m_checkReply, &QNetworkReply::readyRead, this,
            [this]() {
                collectBoundedReply(
                    m_checkReply, m_checkBody, kMaxReleaseMetadataBytes);
            });
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
    collectBoundedReply(reply, m_checkBody, kMaxReleaseMetadataBytes);
    const bool invalidRedirect =
        reply->property("pixiuInvalidRedirect").toBool();
    const bool tooLarge = reply->property("pixiuTooLarge").toBool();
    const bool ok = reply->error() == QNetworkReply::NoError;
    const QByteArray body = std::move(m_checkBody);
    m_checkBody.clear();
    reply->deleteLater();

    if (invalidRedirect) {
        setState(State::Failed);
        emit upgradeFinished(false, tr("更新源无效"),
                             FailedReason::InvalidSource);
        return;
    }
    if (!ok || tooLarge) {
        // 传输超时（setTransferTimeout → OperationCanceledError）与网络/HTTP
        // 失败同归「无法连接」路径（非 NoError 即判定失败）。
        qCWarning(lcUpgrade) << "check failed (network/http):" << m_releaseUrl;
        setState(State::Failed);
        emit upgradeFinished(false, tr("无法连接更新服务器"),
                             FailedReason::Network);
        return;
    }

    ui::ReleaseInfo info;
    if (!ui::parseRelease(body, info)) {
        qCWarning(lcUpgrade) << "release/latest parse failed";
        setState(State::Failed);
        emit upgradeFinished(false, tr("无法连接更新服务器"),
                             FailedReason::Network);
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
        emit upgradeFinished(true, tr("已是最新版本"), FailedReason::None);
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
        emit upgradeFinished(false, tr("更新源无效"),
                             FailedReason::InvalidSource);
        return;
    }
    resetTransport();
    setState(State::Downloading);

    QTemporaryFile temporary(
        QStandardPaths::writableLocation(QStandardPaths::TempLocation)
        + QStringLiteral("/pixiu-update-XXXXXX.deb"));
    temporary.setAutoRemove(false);
    if (!temporary.open()) {
        setState(State::Failed);
        emit upgradeFinished(false, tr("下载失败"), FailedReason::Download);
        return;
    }
    m_debPath = temporary.fileName();
    temporary.close();
    QFile::remove(m_debPath);
    m_downloadFile = new QSaveFile(m_debPath);
    if (!m_downloadFile->open(QIODevice::WriteOnly)) {
        delete m_downloadFile;
        m_downloadFile = nullptr;
        QFile::remove(m_debPath);
        setState(State::Failed);
        emit upgradeFinished(false, tr("下载失败"), FailedReason::Download);
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
    protectRedirect(m_downloadReply);
    connect(m_downloadReply, &QNetworkReply::metaDataChanged, this,
            [this]() {
                if (!m_downloadReply) {
                    return;
                }
                const qint64 length = m_downloadReply
                    ->header(QNetworkRequest::ContentLengthHeader)
                    .toLongLong();
                if (length > kMaxPackageBytes) {
                    m_downloadReply->setProperty("pixiuTooLarge", true);
                    m_downloadReply->abort();
                }
            });
    connect(m_downloadReply, &QNetworkReply::readyRead, this, [this]() {
        if (m_downloadFile && m_downloadReply) {
            const QByteArray chunk = m_downloadReply->readAll();
            if (m_downloadBytes + chunk.size() > kMaxPackageBytes) {
                m_downloadReply->setProperty("pixiuTooLarge", true);
                m_downloadReply->abort();
                return;
            }
            if (m_downloadFile->write(chunk) != chunk.size()) {
                m_downloadReply->setProperty("pixiuWriteFailed", true);
                m_downloadReply->abort();
                return;
            }
            m_downloadBytes += chunk.size();
        }
    });
    connect(m_downloadReply, &QNetworkReply::downloadProgress, this,
            [this](qint64 received, qint64 total) {
                if (m_downloadReply
                    && (received > kMaxPackageBytes
                        || total > kMaxPackageBytes)) {
                    m_downloadReply->setProperty("pixiuTooLarge", true);
                    m_downloadReply->abort();
                    return;
                }
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
    if (m_downloadFile && reply->isOpen()) {
        const QByteArray remaining = reply->readAll();
        if (m_downloadBytes + remaining.size() > kMaxPackageBytes) {
            reply->setProperty("pixiuTooLarge", true);
        } else if (m_downloadFile->write(remaining) != remaining.size()) {
            reply->setProperty("pixiuWriteFailed", true);
        } else {
            m_downloadBytes += remaining.size();
        }
    }
    const bool invalidRedirect =
        reply->property("pixiuInvalidRedirect").toBool();
    const bool tooLarge = reply->property("pixiuTooLarge").toBool();
    const bool writeFailed =
        reply->property("pixiuWriteFailed").toBool();
    const bool ok = reply->error() == QNetworkReply::NoError;
    reply->deleteLater();

    // 传输超时（setTransferTimeout → OperationCanceledError）与网络/HTTP 失败
    // 同归「下载失败」路径（非 NoError 即判定失败）。
    if (invalidRedirect || tooLarge || writeFailed || !ok || !m_downloadFile
        || !m_downloadFile->commit()) {
        if (m_downloadFile) {
            m_downloadFile->cancelWriting();
            delete m_downloadFile;
            m_downloadFile = nullptr;
        }
        QFile::remove(m_debPath);
        m_debPath.clear();
        setState(State::Failed);
        emit upgradeFinished(
            false, invalidRedirect ? tr("更新源无效") : tr("下载失败"),
            invalidRedirect ? FailedReason::InvalidSource
                            : FailedReason::Download);
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
    protectRedirect(m_shaReply);
    QNetworkReply *sha = m_shaReply;
    connect(sha, &QNetworkReply::readyRead, this,
            [this, sha]() {
                collectBoundedReply(sha, m_shaBody, kMaxChecksumBytes);
            });
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
    collectBoundedReply(reply, m_shaBody, kMaxChecksumBytes);
    const bool invalidRedirect =
        reply->property("pixiuInvalidRedirect").toBool();
    const bool tooLarge = reply->property("pixiuTooLarge").toBool();
    const bool ok = reply->error() == QNetworkReply::NoError;
    const QByteArray body = std::move(m_shaBody);
    m_shaBody.clear();
    reply->deleteLater();

    if (m_state != State::Verifying) {
        return; // 已取消/失败，忽略迟到回调
    }
    // sha 获取失败（网络错误 / 传输超时 → OperationCanceledError）：并入
    // 「下载失败」路径，与校验不通过区分，避免把网络问题误报为「校验失败」。
    if (invalidRedirect || tooLarge || !ok) {
        QFile::remove(m_debPath);
        m_debPath.clear();
        setState(State::Failed);
        emit upgradeFinished(
            false, invalidRedirect ? tr("更新源无效") : tr("下载失败"),
            invalidRedirect ? FailedReason::InvalidSource
                            : FailedReason::Download);
        return;
    }
    const QString expected = QString::fromLatin1(body);
    m_expectedSha256 =
        ui::sha256FromManifest(expected, m_release.debName);
    if (m_expectedSha256.isEmpty()
        || !ui::verifySha256(m_debPath, expected, m_release.debName)) {
        QFile::remove(m_debPath);
        m_debPath.clear();
        setState(State::Failed);
        emit upgradeFinished(false, tr("校验失败，已中止"),
                             FailedReason::Verify);
        return;
    }
    startInstall();
}

void UpgradeController::startInstall()
{
    setState(State::Installing);
    m_installErrorOutput.clear();

    const QStringList args{
        QStringLiteral("/usr/lib/pixiu/install-update"),
        m_debPath,
        m_expectedSha256,
    };
    if (m_installRunner) {
        // test seam：注入的执行器记录 program/argv 并自行回调退出码。
        m_installRunner(m_installProgram, args, [this](int exitCode) {
            handleInstallFinished(exitCode);
        });
        return;
    }

    m_installProcess = new QProcess(this);
    m_installProcess->setProcessChannelMode(QProcess::SeparateChannels);
    connect(m_installProcess,
            QOverload<int, QProcess::ExitStatus>::of(&QProcess::finished),
            this, [this](int exitCode, QProcess::ExitStatus) {
                if (m_installProcess) {
                    m_installErrorOutput = QString::fromLocal8Bit(
                        m_installProcess->readAllStandardError());
                }
                handleInstallFinished(exitCode);
            });
    connect(m_installProcess, &QProcess::errorOccurred, this,
            [this](QProcess::ProcessError error) {
                if (error == QProcess::FailedToStart
                    && m_state == State::Installing) {
                    failInstall(tr("无法启动系统安装程序"));
                }
            });
    m_installProcess->setProgram(m_installProgram);
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
        emit upgradeFinished(true, tr("升级成功，请手动重启应用以生效"),
                             FailedReason::None);
    } else if (exitCode == 126 || exitCode == 127) {
        setState(State::Cancelled);
        emit upgradeFinished(false, tr("已取消，升级未执行"),
                             FailedReason::Other);
    } else if (exitCode == 4) {
        setState(State::Failed);
        emit upgradeFinished(false, tr("升级后健康检查失败，已停止继续操作"),
                             FailedReason::Health);
    } else {
        QString detail = m_installErrorOutput.simplified().left(300);
        failInstall(
            detail.isEmpty() ? tr("升级失败，请检查系统日志")
                             : tr("升级失败：%1").arg(detail));
    }
}

void UpgradeController::cancel()
{
    switch (m_state) {
    case State::Downloading:
    case State::Verifying:
        break;
    default:
        return; // 仅下载/校验中可取消
    }
    setState(State::Cancelled);
    resetTransport();
    emit upgradeFinished(false, tr("已取消"), FailedReason::Other);
}

void UpgradeController::protectRedirect(QNetworkReply *reply)
{
    connect(reply, &QNetworkReply::redirected, this,
            [this, reply](const QUrl &target) {
                const QUrl resolved = reply->url().resolved(target);
                if (!m_sourceValidator(resolved)) {
                    reply->setProperty("pixiuInvalidRedirect", true);
                    reply->abort();
                }
            });
}

void UpgradeController::collectBoundedReply(
    QNetworkReply *reply, QByteArray &target, qint64 maximumBytes)
{
    if (!reply || !reply->isOpen()
        || reply->property("pixiuTooLarge").toBool()) {
        return;
    }
    const QByteArray chunk = reply->readAll();
    if (target.size() + chunk.size() > maximumBytes) {
        reply->setProperty("pixiuTooLarge", true);
        reply->abort();
        return;
    }
    target.append(chunk);
}

void UpgradeController::failInstall(const QString &message)
{
    if (m_state != State::Installing) {
        return;
    }
    if (m_installProcess) {
        m_installProcess->disconnect(this);
        m_installProcess->deleteLater();
        m_installProcess = nullptr;
    }
    if (!m_debPath.isEmpty()) {
        QFile::remove(m_debPath);
        m_debPath.clear();
    }
    setState(State::Failed);
    emit upgradeFinished(false, message, FailedReason::Install);
}
