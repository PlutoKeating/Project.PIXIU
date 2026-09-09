#include "SettingsWorkspace.h"
#include "widgets/WorkspaceNavigation.h"
#include <QScrollArea>
#include "PrivacyPage.h"
#include "ServiceStatusPage.h"
#include "HostCloseGuard.h"
#include "HostTray.h"
#include "HostWindowPin.h"
#include "widgets/CheckUpdateDialog.h"
#include "widgets/InfoDialog.h"
#include "app/ProductInformation.h"
#include "services/HttpBackendTransport.h"
#include <QComboBox>
#include <QLineEdit>
#include <QJsonArray>
#include <QCoreApplication>
#include <QCheckBox>
#include <QSignalBlocker>
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
    general->setMaximumWidth(780);
    auto *generalLayout = new QVBoxLayout(general);
    generalLayout->setContentsMargins(28, 24, 28, 24);
    generalLayout->setSpacing(12);
    auto heading = [general, generalLayout](const QString &text) {
        auto *label = new QLabel(text, general);
        label->setStyleSheet("font-size: 16px; font-weight: 600; padding-top: 12px;");
        generalLayout->addWidget(label);
    };
    heading(tr("助手与记忆"));
    auto *agent = new QPushButton(tr("配置模型…"), general);
    agent->setObjectName(QStringLiteral("agentSettings"));
    generalLayout->addWidget(agent);
    connect(agent, &QPushButton::clicked, this, &SettingsWorkspace::agentSettingsRequested);
    auto *memoryHttp = new HttpBackendTransport(this);
    auto *capture = new QCheckBox(tr("允许助手使用本机已授权采集的记忆"), general);
    capture->setObjectName("agentReadCapture");
    auto *shared = new QCheckBox(tr("允许助手查询共享空间"), general);
    shared->setObjectName("agentReadShared");
    auto *space = new QLineEdit(QStringLiteral("shared:home"), general);
    space->setAccessibleName(tr("共享空间名称"));
    auto *saveTo = new QComboBox(general);
    saveTo->setObjectName("agentSaveDestination");
    saveTo->addItem(tr("新记忆仅自己可用"), QStringLiteral("user:local"));
    saveTo->addItem(tr("新记忆保存到上面的共享空间"), QStringLiteral("shared"));
    auto *saveMemory = new QPushButton(tr("保存助手记忆设置"), general);
    auto *memoryStatus = new QLabel(tr("正在读取记忆设置…"), general);
    memoryStatus->setWordWrap(true);
    for (auto *widget : QList<QWidget *>{capture, shared, space, saveTo, saveMemory, memoryStatus})
        generalLayout->addWidget(widget);
    saveMemory->setEnabled(false);
    connect(memoryHttp, &HttpBackendTransport::agentMemorySettingsResult, this, [=](const QJsonObject &value) {
        capture->setChecked(value.value("include_capture").toBool(true));
        const auto scopes = value.value("shared_scopes").toArray();
        shared->setChecked(!scopes.isEmpty());
        if (!scopes.isEmpty()) {
            QStringList names;
            for (const auto &entry : scopes) names << entry.toString();
            space->setText(names.join(","));
        }
        const auto write = value.value("write_scope").toString();
        if (write.startsWith("shared:")) saveTo->setCurrentIndex(1);
        else {
            saveTo->setCurrentIndex(0);
            saveTo->setItemData(0, write.isEmpty()
                ? qEnvironmentVariable("PIXIU_AGENT_SCOPE", "user:default") : write);
        }
        saveMemory->setEnabled(true);
        memoryStatus->setText(tr("已生效。读取范围与新记忆保存位置分别设置；已有记录不会搬动。"));
    });
    connect(saveMemory, &QPushButton::clicked, this, [=]() {
        QJsonArray scopes;
        const auto names = space->text().split(',', Qt::SkipEmptyParts);
        if (shared->isChecked()) for (const auto &name : names) scopes.append(name.trimmed());
        const QString destination = saveTo->currentIndex() == 1
            ? (names.isEmpty() ? QString() : names.first().trimmed()) : saveTo->currentData().toString();
        saveMemory->setEnabled(false);
        memoryHttp->saveAgentMemorySettings({{"include_capture", capture->isChecked()},
            {"shared_scopes", scopes}, {"write_scope", destination}});
    });
    connect(memoryHttp, &BackendTransport::errorOccurred, this, [=](const QString &, const QString &, const QString &) {
        saveMemory->setEnabled(true);
        memoryStatus->setText(tr("记忆设置未保存，请检查服务连接及共享空间名称后重试。"));
    });
    memoryHttp->agentMemorySettings();
    heading(tr("桌面使用"));
    auto *animations = new QCheckBox(tr("界面动画"), general);
    animations->setObjectName("interfaceAnimations");
    animations->setToolTip(tr("关闭后立即切换界面，减少低配置电脑的绘制开销。"));
    animations->setChecked(MotionPreferences::enabled());
    generalLayout->addWidget(animations);
    connect(animations, &QCheckBox::toggled, this, [](bool enabled) {
        MotionPreferences::setEnabled(enabled);
    });
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
    auto *pin = new QCheckBox(tr("主窗口置顶（不更改启动配置）"), general);
    pin->setObjectName(QStringLiteral("hostWindowPin"));
    auto *pinStatus = new QLabel(general);
    pinStatus->setObjectName(QStringLiteral("hostWindowPinStatus"));
    pinStatus->setWordWrap(true);
    pinStatus->setTextFormat(Qt::PlainText);
    generalLayout->addWidget(pin);
    generalLayout->addWidget(pinStatus);
    auto *windowPin = window()->findChild<HostWindowPin *>(QString(), Qt::FindDirectChildrenOnly);
    if (windowPin) {
        auto updatePin = [windowPin, pin, pinStatus]() {
            const QSignalBlocker blocker(pin);
            pin->setEnabled(windowPin->available() && !windowPin->pending());
            pin->setChecked(windowPin->available() && windowPin->pinned());
            pinStatus->setText(windowPin->status());
        };
        connect(windowPin, &HostWindowPin::changed, pin, updatePin);
        connect(pin, &QCheckBox::toggled, windowPin, &HostWindowPin::setPinned);
        updatePin();
    } else {
        pin->setEnabled(false);
        pinStatus->setText(tr("宿主窗口服务不可用，未更改置顶状态。"));
    }
    heading(tr("关于与更新"));
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
    for (auto *button : general->findChildren<QPushButton *>(QString(), Qt::FindDirectChildrenOnly))
        generalLayout->setAlignment(button, Qt::AlignLeft);
    auto *generalScroll = new QScrollArea(tabs);
    generalScroll->setWidgetResizable(true);
    generalScroll->setFrameShape(QFrame::NoFrame);
    generalScroll->setWidget(general);
    tabs->addTab(generalScroll, tr("应用与升级"));
    tabs->addTab(new PrivacyPage(tabs), tr("采集与隐私"));
    tabs->addTab(new ServiceStatusPage(tabs), tr("服务与能力"));
    installWorkspaceNavigation(layout, tabs, {tr("应用与升级"), tr("采集与隐私"), tr("服务与能力")});
}
bool SettingsWorkspace::hasUnsavedChanges() const
{
    return m_tray && (m_shortcutSaveFailed
        || m_activationShortcut->keySequence() != m_tray->activationShortcut());
}
}
