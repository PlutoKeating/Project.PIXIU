#include "app/PixiuApp.h"

#include "app/SingleInstanceGuard.h"
#include "app/TrayIcon.h"
#include "app/AppSettings.h"
#include "app/ShortcutManager.h"
#include "app/QueryController.h"
#include "app/WriteController.h"
#include "app/ForgetController.h"
#include "app/ConflictController.h"
#include "app/PreferenceController.h"
#include "app/SyncController.h"
#include "app/EventRouter.h"
#include "app/ThemeService.h"
#include "widgets/FloatingBall.h"
#include "widgets/ChatWindow.h"
#include "widgets/ImportDialog.h"
#include "widgets/ForgetDialog.h"
#include "widgets/SettingsDialog.h"
#include "widgets/MemoryPanel.h"
#include "widgets/MessageList.h"
#include "models/ChatMessage.h"
#include "models/MemoryAtom.h"
#include "services/BackendTransport.h"
#include "services/HttpBackendTransport.h"
#include "services/NotifyService.h"
#include "services/WebSocketClient.h"

#include <QLoggingCategory>
#include <QCoreApplication>
#include <QDateTime>
#include <QGuiApplication>
#include <QJsonObject>
#include <QScreen>

Q_LOGGING_CATEGORY(lcApp, "pixiu.app")

// 私有实现：后续 feature（单实例、托盘、设置、服务与窗口）在此挂载。
struct PixiuApp::Private
{
    // Phase 1B 暂无成员；后续以 QScopedPointer 持有服务与窗口对象。
};

PixiuApp::PixiuApp(QObject *parent)
    : QObject(parent)
    , d(new Private())
{
}

PixiuApp::~PixiuApp() = default;

bool PixiuApp::start()
{
    qCInfo(lcApp) << "PIXIU application starting";

    // 单实例守护：重复启动时请求唤起已有实例并让本进程退出。
    m_instanceGuard = new SingleInstanceGuard(this);
    if (!m_instanceGuard->tryStart()) {
        qCInfo(lcApp) << "exiting: another instance is already running";
        return false;
    }

    // 主题跟随：UKUI 明暗切换时同步应用 Palette；无 KYSDK 时静态降级。
    m_themeService = new ThemeService(this);
    if (!m_themeService->start()) {
        qCInfo(lcApp) << "theme following disabled; using Qt default palette";
    }

    // 系统托盘：打开主入口 + 显式退出。
    m_tray = new TrayIcon(this);
    if (m_tray->show()) {
        connect(m_tray, &TrayIcon::quitRequested, this, &PixiuApp::shutdown);
        connect(m_tray, &TrayIcon::quitRequested, QCoreApplication::quit);
    } else {
        m_tray->deleteLater();
        m_tray = nullptr;
    }

    // 桌面通知：托盘可用时展示系统通知，否则降级为日志。
    m_notify = new NotifyService(this);
    if (m_tray) {
        m_notify->setTrayIcon(m_tray->trayIcon());
    }

    // 基础设置持久化：记录最近一次启动时间，验证读写链路。
    m_settings = new AppSettings(this);
    const qint64 lastLaunched =
        m_settings->value(AppSettings::keyLastLaunched, QVariant::fromValue(qint64(0))).toLongLong();
    if (lastLaunched > 0) {
        qCInfo(lcApp) << "previous launch timestamp:" << lastLaunched;
    }
    m_settings->setValue(AppSettings::keyLastLaunched,
                         QDateTime::currentSecsSinceEpoch());
    m_settings->sync();

    // 悬浮球：常驻桌面入口（默认屏幕右下角；位置持久化在下一 feature）。
    m_floatingBall = new FloatingBall();
    const QVariant savedPos = m_settings->value(AppSettings::keyBallPosition);
    if (savedPos.isValid()) {
        m_floatingBall->restorePosition(savedPos.toPoint());
    } else if (QScreen *screen = QGuiApplication::primaryScreen()) {
        const QRect screenRect = screen->availableGeometry();
        m_floatingBall->move(screenRect.right() - m_floatingBall->width() - 24,
                             screenRect.bottom() - m_floatingBall->height() - 24);
    }
    connect(m_floatingBall, &FloatingBall::movedTo, this, [this](const QPoint &pos) {
        m_settings->setValue(AppSettings::keyBallPosition, pos);
        m_settings->sync();
    });
    m_floatingBall->show();

    // 聊天主窗口：默认屏幕右下角弹出（悬浮球附近）。
    m_chatWindow = new ChatWindow();
    if (QScreen *screen = QGuiApplication::primaryScreen()) {
        const QRect screenRect = screen->availableGeometry();
        m_chatWindow->move(screenRect.right() - m_chatWindow->width() - 24,
                           screenRect.bottom() - m_chatWindow->height() - 24);
    }

    // 各入口统一唤起聊天框。
    connect(m_floatingBall, &FloatingBall::clicked, this, &PixiuApp::toggleChatWindow);
    connect(m_chatWindow, &ChatWindow::closeRequested,
            m_chatWindow, &ChatWindow::hideAnimated);
    connect(m_chatWindow, &ChatWindow::sendRequested, this,
            [this](const QString &text) {
                if (ForgetController::isForgetIntent(text)) {
                    ChatMessage user;
                    user.role = MessageRole::User;
                    user.text = text;
                    user.timestamp = QDateTime::currentSecsSinceEpoch();
                    m_chatWindow->messageList()->appendMessage(user);
                    m_forgetController->requestConfirmation(text);
                    return;
                }
                if (m_queryController) {
                    m_queryController->submit(text);
                }
            });
    m_memoryPanel = new MemoryPanel();
    const auto openMemoryPanel = [this]() {
        if (m_conflictController) {
            m_memoryPanel->setConflictsLoading();
            m_conflictController->refresh();
        }
        if (m_syncController) {
            m_syncController->refresh();
        }
        m_memoryPanel->showAndFocus();
    };
    connect(m_chatWindow, &ChatWindow::openPanelRequested, this, openMemoryPanel);
    connect(m_floatingBall, &FloatingBall::openPanelRequested, this, openMemoryPanel);
    connect(m_chatWindow, &ChatWindow::settingsRequested,
            this, &PixiuApp::openSettings);
    connect(m_floatingBall, &FloatingBall::settingsRequested,
            this, &PixiuApp::openSettings);
    connect(m_floatingBall, &FloatingBall::quitRequested, this, &PixiuApp::shutdown);
    connect(m_floatingBall, &FloatingBall::quitRequested, QCoreApplication::quit);
    connect(m_instanceGuard, &SingleInstanceGuard::activationRequested,
            m_chatWindow, &ChatWindow::showAndFocus);
    if (m_tray) {
        connect(m_tray, &TrayIcon::openRequested,
                m_chatWindow, &ChatWindow::showAndFocus);
    }

    // 开发态全局快捷键唤起。
    m_shortcutManager = new ShortcutManager(m_chatWindow, this);
    const QKeySequence toggleShortcut(
        m_settings->value(AppSettings::keyToggleShortcut,
                          QStringLiteral("Ctrl+Alt+P")).toString());
    if (m_shortcutManager->registerToggleShortcut(toggleShortcut)) {
        connect(m_shortcutManager, &ShortcutManager::toggleRequested,
                this, &PixiuApp::toggleChatWindow);
    }

    // 后端传输：HTTP transport（查询/写入/管理端点）。
    m_transport = new HttpBackendTransport(this);
    connect(m_transport, &BackendTransport::connectionStateChanged,
            m_chatWindow, &ChatWindow::setBackendState);

    // 设备配对（Phase 6 壳）：UI 与契约载荷已就绪；后端 /sync/pair 落地后
    // 真实闭环，当前如实呈现 not_implemented / 网络错误，不伪造成功。
    connect(m_memoryPanel, &MemoryPanel::pairRequested, this,
            [this](const QJsonObject &payload) {
                m_pairPending = true;
                m_transport->pairDevice(payload);
            });
    connect(m_transport, &BackendTransport::pairResult, this,
            [this](const QJsonObject &response) {
                m_pairPending = false;
                const QString status =
                    response.value(QStringLiteral("status")).toString();
                if (status == QStringLiteral("not_implemented")) {
                    m_memoryPanel->setSyncStatus(
                        tr("配对接口待后端实现（Phase 6）"));
                    return;
                }
                // 契约成功态为 "paired"（docs/API.md §3.8）；其余状态如实
                // 呈现为失败，避免把后端错误响应误报为成功。
                if (status != QStringLiteral("paired")) {
                    m_memoryPanel->setSyncStatus(
                        tr("配对请求失败：%1").arg(
                            status.isEmpty() ? tr("未知响应") : status));
                    return;
                }
                const QString peer =
                    response.value(QStringLiteral("device_name")).toString();
                m_memoryPanel->setSyncStatus(
                    tr("配对成功：%1").arg(peer.isEmpty() ? tr("设备") : peer),
                    true);
            });
    connect(m_transport, &BackendTransport::errorOccurred, this,
            [this](const QString &code, const QString &message, const QString &) {
                if (!m_pairPending) {
                    return;
                }
                m_pairPending = false;
                m_memoryPanel->setSyncStatus(
                    tr("配对请求失败（%1）：%2").arg(code, message));
            });

    // 同步管理：节点列表 / 同步状态 / 解绑（Phase 6）。
    // 后端占位返回 not_implemented 时如实呈现，不伪造节点或成功状态。
    m_syncController = new SyncController(m_transport, this);
    connect(m_memoryPanel, &MemoryPanel::syncRefreshRequested,
            m_syncController, &SyncController::refresh);
    connect(m_memoryPanel, &MemoryPanel::revokeConfirmed,
            m_syncController, &SyncController::revokePeer);
    connect(m_syncController, &SyncController::peersLoaded, this,
            [this](const QJsonArray &peers) {
                m_memoryPanel->setPeers(peers);
                m_memoryPanel->setSyncStatus(tr("同步状态已刷新"), true);
            });
    connect(m_syncController, &SyncController::syncStatusLoaded, this,
            [this](const QJsonObject &status) {
                m_memoryPanel->setSyncSummary(status);
            });
    connect(m_syncController, &SyncController::revoked, this,
            [this](const QString &peerId) {
                m_memoryPanel->setSyncStatus(tr("已解绑设备 %1").arg(peerId), true);
                m_syncController->refresh();
            });
    connect(m_syncController, &SyncController::notImplemented, this,
            [this](const QString &feature) {
                if (feature == QStringLiteral("revoke")) {
                    m_memoryPanel->setSyncStatus(
                        tr("解绑接口待后端实现（Phase 6）"));
                } else {
                    m_memoryPanel->setSyncStatus(
                        tr("节点列表与同步状态待后端实现（Phase 6）"));
                }
            });
    connect(m_syncController, &SyncController::failed, this,
            [this](const QString &code, const QString &message) {
                m_memoryPanel->setSyncStatus(
                    tr("同步刷新失败（%1）：%2").arg(code, message));
            });

    // 查询状态机：加载/取消/失败/重试。
    m_queryController = new QueryController(m_transport, this);
    connect(m_queryController, &QueryController::userMessageReady, this,
            [this](const QString &text) {
                ChatMessage message;
                message.role = MessageRole::User;
                message.text = text;
                message.timestamp = QDateTime::currentSecsSinceEpoch();
                m_chatWindow->messageList()->appendMessage(message);
            });
    connect(m_queryController, &QueryController::thinkingChanged, this,
            [this](bool thinking) {
                m_chatWindow->messageList()->setThinking(thinking);
            });
    connect(m_queryController, &QueryController::answerReady, this,
            [this](const MemoryAtom &memory) {
                ChatMessage reply;
                reply.role = MessageRole::Assistant;
                reply.text = memory.answer;
                reply.evidenceId = memory.sourceEvidence.isEmpty()
                                       ? QString()
                                       : memory.sourceEvidence.first();
                reply.confidence = memory.confidence;
                reply.latencyMs = memory.latencyMs;
                reply.timestamp = QDateTime::currentSecsSinceEpoch();
                m_chatWindow->messageList()->appendMessage(reply);
            });
    connect(m_queryController, &QueryController::emptyResultReady, this,
            [this]() {
                m_chatWindow->messageList()->appendEmptyResult(
                    tr("未找到相关记忆，换个说法试试，或录入新知识。"));
            });
    connect(m_queryController, &QueryController::queryFailed, this,
            [this](const QString &text, const QString &code, const QString &message) {
                const QString detail =
                    tr("查询失败（%1）：%2\n输入已保留，可修改后重试。")
                        .arg(code, message);
                m_chatWindow->messageList()->appendQueryError(text, detail);
                m_chatWindow->restoreInput(text);
            });
    connect(m_chatWindow->messageList(), &MessageList::retryRequested, this,
            [this](const QString &text) {
                m_queryController->submit(text);
            });
    connect(m_chatWindow->messageList(), &MessageList::evidenceClicked, this,
            [this](const QString &evidenceId) {
                ChatMessage notice;
                notice.role = MessageRole::System;
                notice.text = tr("证据详情接口待后端提供（source_evidence=%1）")
                                  .arg(evidenceId);
                notice.timestamp = QDateTime::currentSecsSinceEpoch();
                m_chatWindow->messageList()->appendMessage(notice);
            });
    connect(m_transport, &BackendTransport::queryResult, m_queryController,
            &QueryController::handleQueryResult);
    connect(m_transport, &BackendTransport::queryFailed, m_queryController,
            &QueryController::handleQueryError);

    // 写入控制器 + 录入对话框。
    m_writeController = new WriteController(m_transport, this);
    m_importDialog = new ImportDialog();
    connect(m_chatWindow, &ChatWindow::attachRequested,
            m_importDialog, &QDialog::show);
    connect(m_chatWindow->messageList(), &MessageList::importKnowledgeRequested, this,
            [this]() {
                m_importDialog->show();
                m_importDialog->raise();
                m_importDialog->activateWindow();
            });
    connect(m_importDialog, &ImportDialog::importRequested, this,
            [this](const QString &title, const QString &content,
                   const QString &scope, const QString &imagePath) {
                if (!m_writeController->submit(
                        title, content, scope, imagePath)) {
                    // 上一条仍在写入：不重复提交，给出明确反馈。
                    ChatMessage notice;
                    notice.role = MessageRole::System;
                    notice.text = tr(
                        "上一条记忆仍在写入，本次录入已跳过，请稍候重试。");
                    notice.timestamp = QDateTime::currentSecsSinceEpoch();
                    m_chatWindow->messageList()->appendMessage(notice);
                }
            });
    connect(m_writeController, &WriteController::writeAccepted, this,
            [this](const QJsonObject &response) {
                ChatMessage notice;
                notice.role = MessageRole::System;
                notice.text = tr("已沉淀：证据 %1 · 质量评分 %2 · 敏感度 %3")
                                  .arg(response.value(QStringLiteral("evidence_id")).toString(),
                                       QString::number(
                                           response.value(QStringLiteral("quality_score")).toDouble(),
                                           'f', 2),
                                       QString::number(
                                           response.value(QStringLiteral("sensitivity")).toInt()));
                notice.timestamp = QDateTime::currentSecsSinceEpoch();
                m_chatWindow->messageList()->appendMessage(notice);
            });
    connect(m_writeController, &WriteController::writeFailed, this,
            [this](const QString &code, const QString &message) {
                ChatMessage notice;
                notice.role = MessageRole::System;
                notice.text = tr("录入失败（%1）：%2").arg(code, message);
                notice.timestamp = QDateTime::currentSecsSinceEpoch();
                m_chatWindow->messageList()->appendMessage(notice);
            });

    // 遗忘两段式确认：先展示影响范围，确认后才执行。
    m_forgetController = new ForgetController(m_transport, this);
    m_forgetDialog = new ForgetDialog();
    connect(m_forgetController, &ForgetController::confirmationReady, this,
            [this](const QString &, const QJsonObject &response) {
                m_forgetDialog->setForgetTargets(
                    response.value(QStringLiteral("targets")).toArray(),
                    response.value(QStringLiteral("cascade")).toObject());
                m_forgetDialog->show();
                m_forgetDialog->raise();
                m_forgetDialog->activateWindow();
            });
    connect(m_forgetDialog, &ForgetDialog::confirmed,
            m_forgetController, &ForgetController::confirm);
    connect(m_forgetDialog, &ForgetDialog::cancelled,
            m_forgetController, &ForgetController::cancel);
    // 远端遗忘确认（WS forget_confirmation）：确认后直接执行第二阶段。
    connect(m_forgetDialog, &ForgetDialog::confirmed, this, [this]() {
        if (m_remoteForgetCommand.isEmpty()) {
            return;
        }
        m_forgetController->confirmRemote(m_remoteForgetCommand);
        m_remoteForgetCommand.clear();
    });
    connect(m_forgetDialog, &ForgetDialog::cancelled, this, [this]() {
        m_remoteForgetCommand.clear();
    });
    connect(m_forgetController, &ForgetController::forgotten, this,
            [this](const QJsonObject &response) {
                const int forgottenCount =
                    response.value(QStringLiteral("forgotten_ids")).toArray().size();
                ChatMessage notice;
                notice.role = MessageRole::System;
                notice.text = tr("已遗忘 %1 条记忆，相关证据与关系已清理。")
                                  .arg(forgottenCount);
                notice.timestamp = QDateTime::currentSecsSinceEpoch();
                m_chatWindow->messageList()->appendMessage(notice);
            });
    connect(m_forgetController, &ForgetController::failed, this,
            [this](const QString &code, const QString &message) {
                ChatMessage notice;
                notice.role = MessageRole::System;
                notice.text = tr("遗忘操作失败（%1）：%2").arg(code, message);
                notice.timestamp = QDateTime::currentSecsSinceEpoch();
                m_chatWindow->messageList()->appendMessage(notice);
            });

    // 冲突审计：面板每次打开时刷新 GET /conflicts。
    m_conflictController = new ConflictController(m_transport, this);
    connect(m_conflictController, &ConflictController::conflictsLoaded, this,
            [this](const QJsonArray &conflicts) {
                m_memoryPanel->setConflicts(conflicts);
            });
    connect(m_conflictController, &ConflictController::failed, this,
            [this](const QString &code, const QString &message) {
                qCWarning(lcApp) << "conflicts load failed:" << code << message;
                m_memoryPanel->setConflictsError(
                    tr("冲突加载失败（%1）：%2").arg(code, message));
            });
    connect(m_memoryPanel, &MemoryPanel::conflictRetryRequested, this,
            [this]() {
                if (m_conflictController) {
                    m_memoryPanel->setConflictsLoading();
                    m_conflictController->refresh();
                }
            });
    m_conflictController->refresh();

    // 偏好历史：面板内输入偏好 ID 后加载版本历史。
    m_preferenceController = new PreferenceController(m_transport, this);
    connect(m_memoryPanel, &MemoryPanel::historyRequested, this,
            [this](const QString &preferenceId) {
                m_lastPreferenceId = preferenceId;
                m_memoryPanel->setPreferenceHistoryLoading();
                m_preferenceController->loadHistory(preferenceId);
            });
    connect(m_preferenceController, &PreferenceController::historyLoaded, this,
            [this](const QJsonObject &response) {
                m_memoryPanel->setPreferenceHistory(response);
            });
    connect(m_preferenceController, &PreferenceController::failed, this,
            [this](const QString &code, const QString &message) {
                qCWarning(lcApp) << "preference history failed:" << code << message;
                m_memoryPanel->setPreferenceHistoryError(
                    tr("偏好历史加载失败（%1）：%2").arg(code, message));
            });
    connect(m_memoryPanel, &MemoryPanel::preferenceRetryRequested, this,
            [this]() {
                if (m_preferenceController && !m_lastPreferenceId.isEmpty()) {
                    m_memoryPanel->setPreferenceHistoryLoading();
                    m_preferenceController->loadHistory(m_lastPreferenceId);
                }
            });

    // WebSocket 事件通道：订阅 /events 推送（memory_ready 等业务事件）。
    m_wsClient = new WebSocketClient(this);
    m_wsClient->setBackendUrl(m_transport->baseUrl());
    connect(m_wsClient, &WebSocketClient::connectionStateChanged, this,
            [](ConnectionState state) {
                qCInfo(lcApp) << "websocket state:" << connectionStateName(state);
            });
    connect(m_wsClient, &WebSocketClient::eventReceived,
            this, &PixiuApp::handleBackendEvent);

    // 业务事件路由：WS 帧 → 语义信号 → 应用行为（通知/角标/面板刷新）。
    m_eventRouter = new EventRouter(this);
    connect(m_eventRouter, &EventRouter::memoryReady, this,
            [this](const QJsonObject &data) {
                qCInfo(lcApp) << "memory ready:"
                              << data.value(QStringLiteral("knowledge_id")).toString()
                              << data.value(QStringLiteral("title")).toString();
                if (m_floatingBall) {
                    m_floatingBall->setUnreadCount(m_floatingBall->unreadCount() + 1);
                }
                if (m_notify) {
                    m_notify->notify(tr("记忆已沉淀"),
                                     data.value(QStringLiteral("title")).toString());
                }
            });
    connect(m_eventRouter, &EventRouter::conflictDetected, this,
            [this](const QString &title, const QString &, const QString &, const QString &) {
                if (m_floatingBall) {
                    m_floatingBall->setUnreadCount(m_floatingBall->unreadCount() + 1);
                }
                if (m_notify) {
                    m_notify->notify(tr("检测到记忆冲突"), title);
                }
                if (m_conflictController) {
                    m_memoryPanel->setConflictsLoading();
                    m_conflictController->refresh();
                }
                if (m_memoryPanel && m_memoryPanel->isVisible()) {
                    m_memoryPanel->showConflictTab();
                }
            });
    connect(m_eventRouter, &EventRouter::forgetConfirmationReady, this,
            [this](const QString &command, const QJsonArray &targets,
                   const QJsonObject &cascade, qint64) {
                m_remoteForgetCommand = command;
                m_forgetDialog->setForgetTargets(targets, cascade);
                m_forgetDialog->show();
                m_forgetDialog->raise();
                m_forgetDialog->activateWindow();
            });
    connect(m_eventRouter, &EventRouter::syncEvent, this,
            [this](const QJsonObject &data) {
                const QString type = data.value(QStringLiteral("type")).toString();
                const QString peer = data.value(QStringLiteral("peer_name")).toString();
                if (m_notify) {
                    m_notify->notify(tr("同步事件"),
                                     peer.isEmpty() ? type : peer);
                }
                if (m_syncController) {
                    m_syncController->refresh();
                }
            });
    // 聊天窗口可见时视为已读，清除悬浮球角标。
    connect(m_chatWindow, &ChatWindow::shown, this, [this]() {
        if (m_floatingBall) {
            m_floatingBall->clearUnread();
        }
    });

    m_transport->connectToBackend();
    m_wsClient->connectToBackend();

    emit started();
    qCInfo(lcApp) << "PIXIU application started";
    return true;
}

void PixiuApp::toggleChatWindow()
{
    if (!m_chatWindow) {
        return;
    }
    if (m_chatWindow->isChatVisible()) {
        m_chatWindow->hideAnimated();
    } else {
        m_chatWindow->showAndFocus();
    }
}

void PixiuApp::openSettings()
{
    if (!m_settingsDialog) {
        m_settingsDialog = new SettingsDialog();
        // 语言偏好持久化；界面语言在下次启动时按显式偏好生效（main.cpp 读取）。
        connect(m_settingsDialog, &QDialog::accepted, this, [this]() {
            m_settings->setValue(AppSettings::keyLanguage,
                                 m_settingsDialog->selectedLanguage());
            const QKeySequence shortcut = m_settingsDialog->selectedShortcut();
            m_settings->setValue(
                AppSettings::keyToggleShortcut,
                shortcut.toString(QKeySequence::PortableText));
            m_settings->sync();
            qCInfo(lcApp) << "language preference saved:"
                          << m_settingsDialog->selectedLanguage();
            // 快捷键修改即时生效：先释放旧序列，再按新序列注册。
            if (m_shortcutManager
                && shortcut != m_shortcutManager->currentSequence()) {
                m_shortcutManager->releaseToggleShortcut();
                m_shortcutManager->registerToggleShortcut(shortcut);
                qCInfo(lcApp) << "toggle shortcut re-registered:"
                              << shortcut.toString(QKeySequence::PortableText);
            }
        });
    }
    m_settingsDialog->setLanguage(
        m_settings->value(AppSettings::keyLanguage).toString());
    m_settingsDialog->setShortcut(
        QKeySequence(m_settings->value(
                         AppSettings::keyToggleShortcut,
                         QStringLiteral("Ctrl+Alt+P"))
                         .toString()));
    m_settingsDialog->showAndFocus();
}

void PixiuApp::handleBackendEvent(const QJsonObject &event)
{
    // 语义分发交由 EventRouter；未知/畸形事件在路由层安全忽略。
    if (m_eventRouter) {
        m_eventRouter->handleEvent(event);
    }
}

void PixiuApp::shutdown()
{
    qCInfo(lcApp) << "PIXIU application shutting down";
    if (m_instanceGuard) {
        m_instanceGuard->stop();
    }
    if (m_shortcutManager) {
        m_shortcutManager->releaseToggleShortcut();
    }
    if (m_wsClient) {
        m_wsClient->disconnectFromBackend();
    }
    emit aboutToShutdown();
}
