#include "app/PixiuApp.h"

#include "app/SingleInstanceGuard.h"
#include "app/TrayIcon.h"
#include "app/AppSettings.h"
#include "app/ShortcutManager.h"
#include "app/QueryController.h"
#include "widgets/FloatingBall.h"
#include "widgets/ChatWindow.h"
#include "widgets/MessageList.h"
#include "models/ChatMessage.h"
#include "models/MemoryAtom.h"
#include "services/BackendTransport.h"
#include "services/HttpBackendTransport.h"

#include <QLoggingCategory>
#include <QCoreApplication>
#include <QDateTime>
#include <QGuiApplication>
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
                if (m_queryController) {
                    m_queryController->submit(text);
                }
            });
    connect(m_chatWindow, &ChatWindow::openPanelRequested, this, []() {
        qCInfo(lcApp) << "memory panel requested (Phase 5)";
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
    m_transport->connectToBackend();

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

void PixiuApp::shutdown()
{
    qCInfo(lcApp) << "PIXIU application shutting down";
    if (m_instanceGuard) {
        m_instanceGuard->stop();
    }
    emit aboutToShutdown();
}
