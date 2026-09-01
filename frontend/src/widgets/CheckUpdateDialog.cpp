#include "widgets/CheckUpdateDialog.h"

#include "app/UiTokens.h"

#include <QCoreApplication>
#include <QHBoxLayout>
#include <QLabel>
#include <QProgressBar>
#include <QPushButton>
#include <QVBoxLayout>

CheckUpdateDialog::CheckUpdateDialog(UpgradeController *controller,
                                     QWidget *parent)
    : QDialog(parent)
    , m_controller(controller)
{
    setObjectName(QStringLiteral("checkUpdateDialog"));
    setWindowTitle(tr("检查更新"));
    // 非模态：与设置/遗忘等弹窗一致，关闭只关本弹窗。
    resize(420, 300);
    setMinimumSize(380, 260);

    QLabel *titleLabel = new QLabel(tr("检查更新"), this);
    titleLabel->setObjectName(QStringLiteral("checkUpdateTitleLabel"));
    titleLabel->setFont(ui::Font::title());
    titleLabel->setAlignment(Qt::AlignLeft);

    m_currentVersionLabel = new QLabel(
        tr("当前版本 %1").arg(QCoreApplication::applicationVersion()), this);
    m_currentVersionLabel->setObjectName(QStringLiteral("currentVersionLabel"));
    m_currentVersionLabel->setFont(ui::Font::body());
    m_currentVersionLabel->setWordWrap(true);

    m_remoteVersionLabel = new QLabel(tr("检测中…"), this);
    m_remoteVersionLabel->setObjectName(QStringLiteral("remoteVersionLabel"));
    m_remoteVersionLabel->setFont(ui::Font::body());
    m_remoteVersionLabel->setWordWrap(true);

    m_updateStatusLabel = new QLabel(tr("正在检查更新…"), this);
    m_updateStatusLabel->setObjectName(QStringLiteral("updateStatusLabel"));
    m_updateStatusLabel->setFont(ui::Font::caption());
    m_updateStatusLabel->setWordWrap(true);

    QLabel *securityHintLabel = new QLabel(
        tr("升级需要系统授权；您的记忆、配置和同步身份将被保留。"), this);
    securityHintLabel->setObjectName(QStringLiteral("updateSecurityHintLabel"));
    securityHintLabel->setFont(ui::Font::caption());
    securityHintLabel->setWordWrap(true);

    m_updateProgressBar = new QProgressBar(this);
    m_updateProgressBar->setObjectName(QStringLiteral("updateProgressBar"));
    m_updateProgressBar->setRange(0, 100);
    m_updateProgressBar->setValue(0);
    m_updateProgressBar->setTextVisible(true);
    m_updateProgressBar->hide();

    // 按钮：检查更新 / 一键升级 / 取消（下载安装中显示）/ 知道了（关闭）。
    m_checkAgainButton = new QPushButton(tr("检查更新"), this);
    m_checkAgainButton->setObjectName(QStringLiteral("checkAgainButton"));
    m_checkAgainButton->setAccessibleName(tr("检查更新"));
    m_checkAgainButton->setCursor(Qt::PointingHandCursor);
    connect(m_checkAgainButton, &QPushButton::clicked, this, [this]() {
        if (m_controller) {
            m_controller->checkForUpdate();
        }
    });

    m_upgradeButton = new QPushButton(tr("一键升级"), this);
    m_upgradeButton->setObjectName(QStringLiteral("upgradeButton"));
    m_upgradeButton->setAccessibleName(tr("一键升级"));
    m_upgradeButton->setCursor(Qt::PointingHandCursor);
    // 未注入控制器：不承诺不存在的升级能力，禁用一键升级。
    m_upgradeButton->setEnabled(m_controller != nullptr);
    connect(m_upgradeButton, &QPushButton::clicked, this, [this]() {
        if (m_controller) {
            m_controller->downloadAndInstall();
        }
    });

    m_cancelButton = new QPushButton(tr("取消"), this);
    m_cancelButton->setObjectName(QStringLiteral("cancelButton"));
    m_cancelButton->setAccessibleName(tr("取消"));
    m_cancelButton->setCursor(Qt::PointingHandCursor);
    m_cancelButton->hide();
    connect(m_cancelButton, &QPushButton::clicked, this, [this]() {
        if (m_controller) {
            m_controller->cancel();
        }
    });

    m_closeButton = new QPushButton(tr("知道了"), this);
    m_closeButton->setObjectName(QStringLiteral("closeButton"));
    m_closeButton->setAccessibleName(tr("知道了"));
    m_closeButton->setCursor(Qt::PointingHandCursor);
    m_closeButton->setDefault(true);
    connect(m_closeButton, &QPushButton::clicked, this, &QDialog::hide);

    QHBoxLayout *buttonRow = new QHBoxLayout();
    buttonRow->addWidget(m_checkAgainButton);
    buttonRow->addWidget(m_upgradeButton);
    buttonRow->addWidget(m_cancelButton);
    buttonRow->addStretch(1);
    buttonRow->addWidget(m_closeButton);

    QVBoxLayout *layout = new QVBoxLayout(this);
    layout->setSpacing(ui::Spacing::M);
    layout->addWidget(titleLabel);
    layout->addWidget(m_currentVersionLabel);
    layout->addWidget(m_remoteVersionLabel);
    layout->addWidget(m_updateStatusLabel);
    layout->addWidget(securityHintLabel);
    layout->addWidget(m_updateProgressBar);
    layout->addStretch(1);
    layout->addLayout(buttonRow);

    if (m_controller) {
        connectController();
    }
}

void CheckUpdateDialog::connectController()
{
    connect(m_controller, &UpgradeController::stateChanged, this,
            &CheckUpdateDialog::onStateChanged);
    connect(m_controller, &UpgradeController::remoteVersionFound, this,
            &CheckUpdateDialog::onRemoteVersionFound);
    connect(m_controller, &UpgradeController::progressChanged, this,
            &CheckUpdateDialog::onProgressChanged);
    connect(m_controller, &UpgradeController::upgradeFinished, this,
            &CheckUpdateDialog::onUpgradeFinished);
}

void CheckUpdateDialog::showAndFocus()
{
    show();
    raise();
    activateWindow();
}

void CheckUpdateDialog::showAndCheck()
{
    showAndFocus();
    if (m_controller) {
        // 每次打开重新检查（UpgradeController 对在途流程防重入）。
        m_controller->checkForUpdate();
    }
}

bool CheckUpdateDialog::operationActive() const
{
    if (!m_controller) {
        return false;
    }
    const UpgradeController::State state = m_controller->state();
    return state == UpgradeController::State::Downloading
        || state == UpgradeController::State::Verifying
        || state == UpgradeController::State::Installing;
}

void CheckUpdateDialog::reject()
{
    if (!operationActive()) {
        QDialog::reject();
    }
}

void CheckUpdateDialog::onStateChanged(UpgradeController::State state)
{
    const bool active = state == UpgradeController::State::Downloading
        || state == UpgradeController::State::Verifying
        || state == UpgradeController::State::Installing;
    m_checkAgainButton->setEnabled(!active);
    m_closeButton->setEnabled(!active);

    switch (state) {
    case UpgradeController::State::Idle:
        // 未来兼容：进入初始 Idle（复位后）重置所有陈旧缓存与 UI，避免
        // 上次检查/下载的残留版本、进度在下次流程开始时闪现旧值。
        m_remoteVersion.clear();
        m_progress = 0;
        m_remoteVersionLabel->setText(tr("检测中…"));
        m_updateStatusLabel->setText(tr("正在检查更新…"));
        m_updateProgressBar->setValue(0);
        m_updateProgressBar->hide();
        m_upgradeButton->setEnabled(false);
        m_cancelButton->hide();
        break;
    case UpgradeController::State::Checking:
        // 关键：每次重新检查必须清空上次的缓存。否则先前 Updatable（如
        // "0.1.6"）后重查 UpToDate，onUpgradeFinished 会据残留 m_remoteVersion
        // 把远程行覆写回旧版本；残余 m_progress 会在 Downloading 短暂显示旧 %。
        m_remoteVersion.clear();
        m_progress = 0;
        m_remoteVersionLabel->setText(tr("检测中…"));
        m_updateStatusLabel->setText(tr("正在检查更新…"));
        m_updateProgressBar->setValue(0);
        m_updateProgressBar->hide();
        m_upgradeButton->setEnabled(false);
        m_cancelButton->hide();
        break;
    case UpgradeController::State::Updatable:
        m_remoteVersionLabel->setText(
            m_remoteVersion.isEmpty() ? tr("检测到新版本")
                                      : tr("远程最新版本 %1").arg(m_remoteVersion));
        m_updateStatusLabel->setText(tr("发现新版本，可一键升级"));
        m_updateProgressBar->hide();
        m_upgradeButton->setEnabled(true);
        m_cancelButton->hide();
        break;
    case UpgradeController::State::UpToDate:
        m_remoteVersionLabel->setText(tr("已是最新"));
        m_updateStatusLabel->setText(tr("已是最新版本"));
        m_updateProgressBar->hide();
        m_upgradeButton->setEnabled(false);
        m_cancelButton->hide();
        break;
    case UpgradeController::State::Downloading:
        m_updateStatusLabel->setText(tr("下载中…%1%").arg(m_progress));
        m_updateProgressBar->setValue(m_progress);
        m_updateProgressBar->show();
        m_upgradeButton->setEnabled(false);
        m_cancelButton->show();
        break;
    case UpgradeController::State::Verifying:
        m_updateStatusLabel->setText(tr("校验正在下载包…"));
        m_updateProgressBar->hide();
        m_upgradeButton->setEnabled(false);
        m_cancelButton->show();
        break;
    case UpgradeController::State::Installing:
        m_updateStatusLabel->setText(tr("正在申请安装权限…"));
        m_updateProgressBar->hide();
        m_upgradeButton->setEnabled(false);
        // dpkg 启动后禁止强制取消，避免留下半配置的软件包。
        m_cancelButton->hide();
        break;
    case UpgradeController::State::Success:
        m_updateStatusLabel->setText(tr("升级成功，请手动重启应用以生效"));
        m_updateProgressBar->hide();
        m_upgradeButton->setEnabled(false);
        m_cancelButton->hide();
        break;
    case UpgradeController::State::Cancelled:
        m_updateStatusLabel->setText(tr("已取消"));
        m_updateProgressBar->hide();
        m_upgradeButton->setEnabled(false);
        m_cancelButton->hide();
        break;
    case UpgradeController::State::Failed:
        m_updateStatusLabel->setText(tr("更新失败"));
        m_updateProgressBar->hide();
        m_upgradeButton->setEnabled(false);
        m_cancelButton->hide();
        break;
    }
}

void CheckUpdateDialog::onRemoteVersionFound(const QString &version)
{
    m_remoteVersion = version;
    m_remoteVersionLabel->setText(tr("远程最新版本 %1").arg(version));
}

void CheckUpdateDialog::onProgressChanged(int percent)
{
    m_progress = percent;
    m_updateProgressBar->setValue(percent);
    m_updateProgressBar->show();
    m_updateStatusLabel->setText(tr("下载中…%1%").arg(percent));
}

void CheckUpdateDialog::onUpgradeFinished(bool success, const QString &message,
                                         UpgradeController::FailedReason reason)
{
    // 终态文案以控制器消息为准（成功提示手动重启 / 各类失败原因精确区分）。
    m_updateStatusLabel->setText(message);
    // 按 reason 而非 message 分发：message 经 tr() 本地化，跨 tr() 上下文
    // 比较会在非中文 locale 分化，静默破坏「网络失败→远程行显示错误」分支。
    // 网络失败无法回填远程版本，远程行直接显示错误文案。
    if (!success && reason == UpgradeController::FailedReason::Network) {
        m_remoteVersionLabel->setText(message);
        return;
    }
    if (!m_remoteVersion.isEmpty()) {
        m_remoteVersionLabel->setText(
            tr("远程最新版本 %1").arg(m_remoteVersion));
    }
}
