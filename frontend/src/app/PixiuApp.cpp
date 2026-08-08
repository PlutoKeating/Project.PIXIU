#include "app/PixiuApp.h"

#include "app/SingleInstanceGuard.h"
#include "app/TrayIcon.h"
#include "app/AppSettings.h"
#include "app/ShortcutManager.h"
#include "app/QueryController.h"
#include "app/WriteController.h"
#include "app/ForgetController.h"
#include "widgets/FloatingBall.h"
#include "widgets/ChatWindow.h"
#include "widgets/ImportDialog.h"
#include "widgets/ForgetDialog.h"
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
    connect(m_chatWindow, &ChatWindow::openPanelRequested, this, [this]() {
        m_memoryPanel->showAndFocus();
    });
    connect(m_instanceGuard, &SingleInstanceGuard::activationRequested,
            m_chatWindow, &ChatWindow::showAndFocus);
    if (m_tray) {
        connect(m_tray, &TrayIcon::openRequested,
                m_chatWindow, &ChatWindow::showAndFocus);
    }

    // 开发态全局快捷键唤起。
    m_shortcutManager = new ShortcutManager(m_chatWindow, this);
    if (m_shortcutManager->registerToggleShortcut()) {
        connect(m_shortcutManager, &ShortcutManager::toggleRequested,
                this, &PixiuApp::toggleChatWindow);
    }

    // 后端传输：HTTP transport（查询/写入/管理端点）。
    m_transport = new HttpBackendTransport(this);
    connect(m_transport, &BackendTransport::connectionStateChanged,
            m_chatWindow, &ChatWindow::setBackendState);

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
                ChatMessage notice;
                notice.role = MessageRole::System;
                notice.text = QStringLiteral("未找到相关记忆，换个说法试试，或录入新知识。");
                notice.timestamp = QDateTime::currentSecsSinceEpoch();
                m_chatWindow->messageList()->appendMessage(notice);
            });
    connect(m_queryController, &QueryController::queryFailed, this,
            [this](const QString &text, const QString &code, const QString &message) {
                ChatMessage notice;
                notice.role = MessageRole::System;
                notice.text = QStringLiteral("查询失败（%1）：%2\n输入已保留，可修改后重试。")
                                  .arg(code, message);
                notice.timestamp = QDateTime::currentSecsSinceEpoch();
                m_chatWindow->messageList()->appendMessage(notice);
                m_chatWindow->restoreInput(text);
            });
    connect(m_chatWindow->messageList(), &MessageList::evidenceClicked, this,
            [this](const QString &evidenceId) {
                ChatMessage notice;
                notice.role = MessageRole::System;
                notice.text = QStringLiteral("证据详情接口待后端提供（source_evidence=%1）")
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
    connect(m_importDialog, &ImportDialog::importRequested,
            m_writeController, &WriteController::submit);
    connect(m_writeController, &WriteController::writeAccepted, this,
            [this](const QJsonObject &response) {
                ChatMessage notice;
                notice.role = MessageRole::System;
                notice.text = QStringLiteral("已沉淀：证据 %1 · 质量评分 %2 · 敏感度 %3")
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
                notice.text = QStringLiteral("录入失败（%1）：%2").arg(code, message);
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
    connect(m_forgetController, &ForgetController::forgotten, this,
            [this](const QJsonObject &response) {
                const int forgottenCount =
                    response.value(QStringLiteral("forgotten_ids")).toArray().size();
                ChatMessage notice;
                notice.role = MessageRole::System;
                notice.text = QStringLiteral("已遗忘 %1 条记忆，相关证据与关系已清理。")
                                  .arg(forgottenCount);
                notice.timestamp = QDateTime::currentSecsSinceEpoch();
                m_chatWindow->messageList()->appendMessage(notice);
            });
    connect(m_forgetController, &ForgetController::failed, this,
            [this](const QString &code, const QString &message) {
                ChatMessage notice;
                notice.role = MessageRole::System;
                notice.text = QStringLiteral("遗忘操作失败（%1）：%2").arg(code, message);
                notice.timestamp = QDateTime::currentSecsSinceEpoch();
                m_chatWindow->messageList()->appendMessage(notice);
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

void PixiuApp::handleBackendEvent(const QJsonObject &event)
{
    const QString name = event.value(QStringLiteral("event")).toString();
    if (name == QStringLiteral("memory_ready")) {
        const QJsonObject data = event.value(QStringLiteral("data")).toObject();
        qCInfo(lcApp) << "memory ready:" << data.value(QStringLiteral("knowledge_id")).toString()
                      << data.value(QStringLiteral("title")).toString();
        if (m_floatingBall) {
            m_floatingBall->setUnreadCount(m_floatingBall->unreadCount() + 1);
        }
        if (m_notify) {
            m_notify->notify(QStringLiteral("记忆已沉淀"),
                             data.value(QStringLiteral("title")).toString());
        }
        return;
    }

    // conflict_detected / forget_confirmation / sync_event 待对应后端广播与
    // 前端 feature 就绪后再接入；此处仅记录，保持前向兼容。
    qCInfo(lcApp) << "business event not yet handled:" << name;
}

void PixiuApp::shutdown()
{
    qCInfo(lcApp) << "PIXIU application shutting down";
    if (m_instanceGuard) {
        m_instanceGuard->stop();
    }
    if (m_wsClient) {
        m_wsClient->disconnectFromBackend();
    }
    emit aboutToShutdown();
}
