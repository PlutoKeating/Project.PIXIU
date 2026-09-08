#include "SettingsWorkspace.h"
#include "PrivacyPage.h"
#include "ServiceStatusPage.h"
#include "HostCloseGuard.h"
#include "HostTray.h"
#include "widgets/CheckUpdateDialog.h"
#include "widgets/InfoDialog.h"
#include "app/ProductInformation.h"
#include <QCoreApplication>
#include <QLabel>
#include <QKeySequenceEdit>
#include <QHBoxLayout>
#include <QPushButton>
#include <QTabWidget>
#include <QVBoxLayout>

namespace pixiu {
SettingsWorkspace::SettingsWorkspace(QWidget *parent) : QWidget(parent)
{
    setObjectName(QStringLiteral("settingsWorkspace"));
    auto *layout = new QVBoxLayout(this);
    layout->setContentsMargins(0, 0, 0, 0);
    auto *tabs = new QTabWidget(this);
    layout->addWidget(tabs);
    auto *general = new QWidget(tabs);
    auto *generalLayout = new QVBoxLayout(general);
    auto *agent = new QPushButton(tr("模型与 Agent 配置…"), general);
    agent->setObjectName(QStringLiteral("agentSettings"));
    generalLayout->addWidget(agent);
    connect(agent, &QPushButton::clicked, this, &SettingsWorkspace::agentSettingsRequested);
    auto *shortcutRow = new QHBoxLayout();
    auto *shortcutLabel = new QLabel(tr("唤起快捷键"), general);
    auto *shortcut = new QKeySequenceEdit(general);
    m_activationShortcut = shortcut;
    shortcut->setObjectName(QStringLiteral("activationShortcut"));
    shortcut->setAccessibleName(tr("唤起 PIXIU 的快捷键"));
    shortcutLabel->setBuddy(shortcut);
    auto *applyShortcut = new QPushButton(tr("应用快捷键"), general);
    applyShortcut->setObjectName(QStringLiteral("applyActivationShortcut"));
    shortcutRow->addWidget(shortcutLabel);
    shortcutRow->addWidget(shortcut, 1);
    shortcutRow->addWidget(applyShortcut);
    generalLayout->addLayout(shortcutRow);
    auto *shortcutStatus = new QLabel(general);
    shortcutStatus->setObjectName(QStringLiteral("activationShortcutStatus"));
    shortcutStatus->setWordWrap(true);
    shortcutStatus->setTextFormat(Qt::PlainText);
    generalLayout->addWidget(shortcutStatus);
    auto *tray = window()->findChild<HostTray *>(QString(), Qt::FindDirectChildrenOnly);
    m_tray = tray;
    shortcut->setEnabled(tray != nullptr);
    applyShortcut->setEnabled(tray != nullptr);
    if (tray) {
        shortcut->setKeySequence(tray->activationShortcut());
        shortcutStatus->setText(tray->shortcutStatus());
        connect(tray, &HostTray::shortcutChanged, shortcutStatus,
            [tray, shortcutStatus]() { shortcutStatus->setText(tray->shortcutStatus()); });
        connect(applyShortcut, &QPushButton::clicked, tray, [this, tray, shortcut, shortcutStatus]() {
            const QString error = tray->setActivationShortcut(shortcut->keySequence());
            m_shortcutSaveFailed = !error.isEmpty() && tray->activationShortcut() == shortcut->keySequence();
            shortcutStatus->setText(error.isEmpty() ? tray->shortcutStatus()
                : error + QStringLiteral("\n") + tray->shortcutStatus());
        });
    } else {
        shortcutStatus->setText(tr("宿主快捷键服务不可用，未修改配置。"));
    }
    auto *version = new QLabel(tr("PIXIU %1").arg(QStringLiteral(PIXIU_VERSION)), general);
    version->setObjectName(QStringLiteral("productVersion"));
    generalLayout->addWidget(version);
    auto *description = new QLabel(tr("PIXIU 记忆系统与 openKylin Agent 集成。升级前请保存正在进行的工作；安装和健康检查成功后，由您选择重启整个应用。"), general);
    description->setWordWrap(true);
    generalLayout->addWidget(description);
    auto *updates = new QPushButton(tr("检查更新"), general);
    updates->setObjectName(QStringLiteral("productUpdates"));
    generalLayout->addWidget(updates);
    auto addInformation = [this, general, generalLayout](const QString &name,
        const QString &title, const QString &body) {
        auto *button = new QPushButton(title, general);
        button->setObjectName(name);
        auto *dialog = new InfoDialog(title, body, this);
        dialog->setObjectName(name + QStringLiteral("Dialog"));
        generalLayout->addWidget(button);
        connect(button, &QPushButton::clicked, dialog, &InfoDialog::showAndFocus);
    };
    addInformation(QStringLiteral("productAbout"), tr("关于 PIXIU"),
        ProductInformation::about(QStringLiteral(PIXIU_VERSION)));
    addInformation(QStringLiteral("productDataUse"), tr("数据与联网说明"), ProductInformation::dataUse());
    addInformation(QStringLiteral("productLicenses"), tr("许可证与第三方组件"), ProductInformation::licenses());
    generalLayout->addStretch();
    auto *upgrade = new UpgradeController(this);
    auto *updateDialog = new CheckUpdateDialog(upgrade, this);
    updateDialog->setRestartConfirmation([this, updateDialog]() {
        auto *guard = window()->findChild<HostCloseGuard *>(QString(), Qt::FindDirectChildrenOnly);
        return guard && guard->confirmExit(updateDialog);
    });
    connect(updates, &QPushButton::clicked, updateDialog, &CheckUpdateDialog::showAndCheck);
    connect(upgrade, &UpgradeController::restartScheduled, QCoreApplication::instance(), &QCoreApplication::quit);
    tabs->addTab(general, tr("应用与升级"));
    tabs->addTab(new PrivacyPage(tabs), tr("采集与隐私"));
    tabs->addTab(new ServiceStatusPage(tabs), tr("服务与能力"));
}
bool SettingsWorkspace::hasUnsavedChanges() const
{
    return m_tray && (m_shortcutSaveFailed
        || m_activationShortcut->keySequence() != m_tray->activationShortcut());
}
}
