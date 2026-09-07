#include "SettingsWorkspace.h"
#include "PrivacyPage.h"
#include "HostCloseGuard.h"
#include "widgets/CheckUpdateDialog.h"
#include <QCoreApplication>
#include <QLabel>
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
    auto *version = new QLabel(tr("PIXIU %1").arg(QStringLiteral(PIXIU_VERSION)), general);
    version->setObjectName(QStringLiteral("productVersion"));
    generalLayout->addWidget(version);
    auto *description = new QLabel(tr("PIXIU 记忆系统与 openKylin Agent 集成。升级前请保存正在进行的工作；安装和健康检查成功后，由您选择重启整个应用。"), general);
    description->setWordWrap(true);
    generalLayout->addWidget(description);
    auto *updates = new QPushButton(tr("检查更新"), general);
    updates->setObjectName(QStringLiteral("productUpdates"));
    generalLayout->addWidget(updates);
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
}
}
