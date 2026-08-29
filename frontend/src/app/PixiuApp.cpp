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
#include "app/Severity.h"
#include "app/ThemeService.h"
#include "app/MonitorController.h"
#include "app/DeliveryController.h"
#include "app/UiTokens.h"
#include "widgets/FloatingBall.h"
#include "widgets/ChatWindow.h"
#include "widgets/ImportDialog.h"
#include "widgets/ForgetDialog.h"
#include "widgets/SettingsDialog.h"
#include "widgets/MemoryPanel.h"
#include "widgets/MonitorCenterDialog.h"
#include "widgets/EvidenceDetailDialog.h"
#include "widgets/MessageList.h"
#include "models/ChatMessage.h"
#include "models/MemoryAtom.h"
#include "services/BackendTransport.h"
#include "services/HttpBackendTransport.h"
#include "services/NotifyService.h"
#include "services/WebSocketClient.h"

#include <QDialog>
#include <QHBoxLayout>
#include <QJsonArray>
#include <QLabel>
#include <QLoggingCategory>
#include <QCoreApplication>
#include <QDateTime>
#include <QGuiApplication>
#include <QJsonObject>
#include <QPushButton>
#include <QRect>
#include <QScreen>
#include <QSet>
#include <QStringList>
#include <QTimer>
#include <QVBoxLayout>

Q_LOGGING_CATEGORY(lcApp, "pixiu.app")

namespace {

// 简单 token 化（B4-3 MVP）：按「非字母/数字」字符切分；CJK 汉字属字母，
// 连续 CJK/ASCII 串成为单个 token（中文无空格分词，整段短语即一个 token）。
// 过滤长度 < 2 的碎片（单字符/单数字噪声）。
QSet<QString> tokenizeForRelevance(const QString &text)
{
    QSet<QString> tokens;
    QString current;
    for (const QChar &ch : text) {
        if (ch.isLetterOrNumber()) {
            current.append(ch);
        } else {
            if (current.size() >= 2) {
                tokens.insert(current);
            }
            current.clear();
        }
    }
    if (current.size() >= 2) {
        tokens.insert(current);
    }
    return tokens;
}

// 两个 token 是否“相关”：相等（大小写不敏感），或一方包含另一方
// （长度 ≥ 2 才参与包含匹配，避免短串/单字符过度命中；CJK 大小写
// 转换是 no-op，不受影响）。
bool tokensRelated(const QString &a, const QString &b)
{
    if (a.compare(b, Qt::CaseInsensitive) == 0) {
        return true;
    }
    if (a.size() >= 2 && b.contains(a, Qt::CaseInsensitive)) {
        return true;
    }
    if (b.size() >= 2 && a.contains(b, Qt::CaseInsensitive)) {
        return true;
    }
    return false;
}

} // namespace

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

void PixiuApp::setTransportForTest(BackendTransport *transport)
{
    // 仅测试用：须在 start() 前调用，start() 检测到已注入则不再创建
    // HttpBackendTransport。transport 所有权仍归调用方（测试对象）。
    // start() 之后 m_transport 已就位，此时再替换会静默丢掉既有
    // transport（所有权归属混乱）——拒绝替换并告警，防止静默覆盖。
    if (m_transport && m_transport != transport) {
        qCWarning(lcApp) << "setTransportForTest: transport already set; "
                            "refusing to replace";
        return;
    }
    m_transport = transport;
}

void PixiuApp::setNotifyServiceForTest(NotifyService *service)
{
    // 仅测试用：须在 start() 前调用，start() 检测到已注入则不再创建默认
    // NotifyService。service 所有权仍归调用方（测试对象），与
    // setTransportForTest 一致；start() 之后替换会静默丢掉既有实例——
    // 拒绝替换并告警，防止静默覆盖。
    if (m_notify && m_notify != service) {
        qCWarning(lcApp) << "setNotifyServiceForTest: notify service already set; "
                            "refusing to replace";
        return;
    }
    m_notify = service;
}

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
    // 测试注入（setNotifyServiceForTest）时复用注入实例，不重复创建。
    if (!m_notify) {
        m_notify = new NotifyService(this);
    }
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
    const QVariant savedWindowGeometry =
        m_settings->value(AppSettings::keyWindowGeometry);
    if (savedWindowGeometry.isValid()) {
        const QRect savedRect = savedWindowGeometry.toRect();
        // 恢复上次位置并钳制到当前可用屏幕区域内（与悬浮球策略一致）。
        // 注意：不能只按 savedRect.topLeft() 是否落在屏幕上决定是否钳制——
        // 显示器分辨率/数量变化后，上次保存的位置可能整体位于屏外
        // （screenAt 对屏外点返回 null），直接 move 会把窗口放到完全不可见、
        // 快捷入口无法点击的位置。统一取所有屏幕可用区域并集做钳制，
        // 保证恢复后的窗口始终完整落在可视区域内。
        QRect area;
        const auto screens = QGuiApplication::screens();
        for (QScreen *screen : screens) {
            area = area.united(screen->availableGeometry());
        }
        if (area.isValid() && !area.isNull()) {
            // 窗口比屏幕还大时（极小分辨率/极大窗口），上限取 max(top, …)
            // 而非负数，保证窗口顶端仍然落在可见区域内、入口可点。
            const int maxX = qMax(area.left(),
                                  area.right() - m_chatWindow->width() + 1);
            const int maxY = qMax(area.top(),
                                  area.bottom() - m_chatWindow->height() + 1);
            const int x = qBound(area.left(), savedRect.x(), maxX);
            const int y = qBound(area.top(), savedRect.y(), maxY);
            m_chatWindow->move(x, y);
        } else {
            m_chatWindow->move(savedRect.topLeft());
        }
    } else if (QScreen *screen = QGuiApplication::primaryScreen()) {
        const QRect screenRect = screen->availableGeometry();
        m_chatWindow->move(screenRect.right() - m_chatWindow->width() - 24,
                           screenRect.bottom() - m_chatWindow->height() - 24);
    }
    // 用户拖动后持久化位置（ARCHITECTURE §5.2“记忆上次位置”）。
    connect(m_chatWindow, &ChatWindow::moved, this,
            [this](const QPoint &topLeft) {
                m_settings->setValue(
                    AppSettings::keyWindowGeometry,
                    QRect(topLeft, m_chatWindow->size()));
                m_settings->sync();
            });

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
        if (m_preferenceController) {
            m_preferenceController->loadList();
        }
        m_memoryPanel->showAndFocus();
    };
    connect(m_chatWindow, &ChatWindow::openPanelRequested, this, openMemoryPanel);
    connect(m_chatWindow, &ChatWindow::syncPanelRequested, this, [this]() {
        if (m_syncController) {
            m_syncController->refresh();
        }
        m_memoryPanel->showSyncTab();
        m_memoryPanel->showAndFocus();
    });
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

    // 监控掌控层：状态单一事实来源 + 三入口（托盘/悬浮球/设置）统一接线。
    // 须置于聊天窗与悬浮球创建之后（回填初始徽标与菜单文案需要它们就绪）。
    m_monitorController = new MonitorController(m_settings, this);
    connect(m_monitorController, &MonitorController::enabledChanged,
            this, &PixiuApp::refreshMonitorUi);
    if (m_tray) {
        connect(m_tray, &TrayIcon::pauseMonitorRequested, this, [this]() {
            m_monitorController->setEnabled(!m_monitorController->isEnabled());
        });
    }
    connect(m_floatingBall, &FloatingBall::pauseMonitorRequested, this,
            [this]() {
                m_monitorController->setEnabled(
                    !m_monitorController->isEnabled());
            });
    connect(m_floatingBall, &FloatingBall::monitorCenterRequested,
            this, &PixiuApp::openMonitorCenter);
    // 初始徽标与托盘/悬浮球菜单文案按已存偏好回填。
    refreshMonitorUi();

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
    // 测试可经 setTransportForTest 注入假 transport（须在 start() 前调用）。
    if (!m_transport) {
        m_transport = new HttpBackendTransport(this);
    }
    connect(m_transport, &BackendTransport::connectionStateChanged,
            m_chatWindow, &ChatWindow::setBackendState);
    // 后端未连接引导（关键状态表）：离线/异常时提示启动服务；每次断线
    // 仅提示一次，恢复在线后复位，避免反复刷屏。
    connect(m_transport, &BackendTransport::connectionStateChanged, this,
            [this](ConnectionState state) {
                const bool offline =
                    state == ConnectionState::Disconnected
                    || state == ConnectionState::Error;
                if (offline && !m_offlineGuidanceShown) {
                    m_offlineGuidanceShown = true;
                    ChatMessage notice;
                    notice.role = MessageRole::System;
                    notice.text = tr(
                        "后端服务未连接，请先启动 PIXIU 后端服务后重试。");
                    notice.timestamp = QDateTime::currentSecsSinceEpoch();
                    m_chatWindow->messageList()->appendMessage(notice);
                    qCInfo(lcApp) << "offline guidance shown";
                } else if (state == ConnectionState::Connected) {
                    m_offlineGuidanceShown = false;
                    // 断线恢复对账：远端配置尚未权威（离线期间拉取/上送
                    // 失败）时重新拉取，避免恢复后本地与远端永久脱节。
                    if (!m_monitorRemoteAuthoritative) {
                        loadRemoteMonitorConfig();
                    }
                }
            });

    // 监控远端契约（A-3）：配置回包覆盖控制器；活动日志回包渲染到面板。
    connect(m_transport, &BackendTransport::configResult, this,
            &PixiuApp::handleMonitorConfigResult);
    connect(m_transport, &BackendTransport::monitorLogResult, this,
            &PixiuApp::handleMonitorLogResult);

    // 设备配对（Phase 6 壳）：UI 与契约载荷已就绪；后端 /sync/pair 落地后
    // 真实闭环，当前如实呈现 not_implemented / 网络错误，不伪造成功。
    connect(m_memoryPanel, &MemoryPanel::pairRequested, this,
            [this](const QJsonObject &payload) {
                m_pairPending = true;
                m_transport->pairDevice(payload);
            });
    // 配对令牌生成（POST /sync/token）：结果路由到配对对话框。
    connect(m_memoryPanel, &MemoryPanel::pairingTokenRequested, this,
            [this](const QJsonObject &payload) {
                m_tokenPending = true;
                m_transport->createPairingToken(payload);
            });
    connect(m_transport, &BackendTransport::pairingTokenResult, this,
            [this](const QJsonObject &response) {
                m_tokenPending = false;
                m_memoryPanel->showPairingToken(response);
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
                if (m_pairPending) {
                    m_pairPending = false;
                    m_memoryPanel->setSyncStatus(
                        tr("配对请求失败（%1）：%2").arg(code, message));
                    return;
                }
                if (m_tokenPending) {
                    m_tokenPending = false;
                    m_memoryPanel->showPairingTokenError(
                        tr("%1：%2").arg(code, message));
                    return;
                }
                if (!m_pendingEvidenceId.isEmpty() && m_evidenceDetailDialog) {
                    m_pendingEvidenceId.clear();
                    m_evidenceDetailDialog->setError(
                        tr("证据加载失败（%1）：%2").arg(code, message));
                    return;
                }
                if (m_monitorConfigPending) {
                    // 监控配置拉取/上送失败：回退本地键并标记非远端权威；
                    // 已打开的面板状态行提示「离线，仅本地生效」。
                    m_monitorConfigPending = false;
                    m_monitorRemoteAuthoritative = false;
                    // 本次 PUT 已失败、无匹配回声可等：清空暂存载荷，避免
                    // 过时载荷毒化后续 GET 处理（GET 失败时载荷本就为空，
                    // 此清空为空操作，覆盖两种场景）。
                    m_monitorPendingPutPayload = QJsonObject();
                    if (m_monitorCenter) {
                        m_monitorCenter->setOfflineHint(true);
                    }
                    return;
                }
            });

    // 递送层（B4-3）：欢迎页动态洞察 + 今日简报。
    // 洞察加载 → 聊天窗渲染动态建议卡（静态兜底保留）；加载时机：启动时
    // 一次 + 聊天窗每次可见时刷新（见 ChatWindow::shown 接线）。
    m_deliveryController = new DeliveryController(m_transport, this);
    connect(m_deliveryController, &DeliveryController::insightsLoaded, this,
            [this](const QJsonArray &insights) {
                m_deliveryInsights = insights;
                if (m_chatWindow) {
                    m_chatWindow->setInsights(insights);
                }
            });
    connect(m_deliveryController, &DeliveryController::digestLoaded, this,
            [this](const QJsonObject &response) {
                if (m_notify) {
                    m_notify->notify(
                        tr("今日简报"),
                        response.value(QStringLiteral("summary")).toString());
                }
            });
    connect(m_deliveryController, &DeliveryController::failed, this,
            [](const QString &code, const QString &message) {
                // 洞察/简报失败不打扰用户：欢迎页保留静态兜底，仅记日志。
                qCWarning(lcApp) << "delivery request failed:"
                                 << code << message;
            });
    connect(m_chatWindow, &ChatWindow::digestRequested, this, [this]() {
        if (m_deliveryController) {
            m_deliveryController->loadDigest();
        }
    });
    m_deliveryController->loadInsights();

    // 同步管理：总开关/暂停/发现/确认式配对/退出网络/立即同步（SN-6）。
    // 后端占位返回 not_implemented 时如实呈现，不伪造节点或成功状态。
    m_syncController = new SyncController(m_transport, this);
    connect(m_memoryPanel, &MemoryPanel::syncRefreshRequested,
            m_syncController, &SyncController::refresh);
    connect(m_memoryPanel, &MemoryPanel::syncSettingsRequested,
            m_syncController, &SyncController::updateSettings);
    connect(m_memoryPanel, &MemoryPanel::syncDiscoverRequested,
            m_syncController, &SyncController::discover);
    connect(m_memoryPanel, &MemoryPanel::syncPairRequested,
            m_syncController, &SyncController::requestPairing);
    connect(m_memoryPanel, &MemoryPanel::syncLeaveRequested,
            this, &PixiuApp::startLeaveNetwork);
    connect(m_memoryPanel, &MemoryPanel::syncNowRequested,
            m_syncController, &SyncController::syncNow);
    connect(m_syncController, &SyncController::peersLoaded, this,
            [this](const QJsonArray &peers) {
                m_syncPeers = peers;
                m_memoryPanel->setPeers(peers);
                m_memoryPanel->setSyncStatus(tr("同步状态已刷新"), true);
            });
    connect(m_syncController, &SyncController::syncStatusLoaded, this,
            [this](const QJsonObject &status) {
                m_memoryPanel->setSyncSummary(status);
                // 初始回填总开关/暂停开关（默认 enabled=true）。
                m_memoryPanel->setSyncSettings(
                    status.value(QStringLiteral("enabled")).toBool(true),
                    status.value(QStringLiteral("paused")).toBool(false));
            });
    connect(m_syncController, &SyncController::discoveredDevices, this,
            [this](const QJsonArray &devices) {
                m_memoryPanel->setDiscoveredDevices(devices);
            });
    connect(m_syncController, &SyncController::settingsResult, this,
            [this](const QJsonObject &response) {
                // PUT 回声回填开关（QSignalBlocker 防回环，见 MemoryPanel）。
                m_memoryPanel->setSyncSettings(
                    response.value(QStringLiteral("enabled")).toBool(true),
                    response.value(QStringLiteral("paused")).toBool(false));
                m_memoryPanel->setSyncStatus(tr("同步设置已更新"), true);
            });
    connect(m_syncController, &SyncController::pairRequestResult, this,
            [this](const QJsonObject &response) {
                m_memoryPanel->setSyncStatus(
                    tr("配对请求已发送，PIN %1").arg(
                        response.value(QStringLiteral("pin")).toString()),
                    true);
            });
    connect(m_syncController, &SyncController::pairConfirmResult, this,
            [this](const QJsonObject &response) {
                const QString status =
                    response.value(QStringLiteral("status")).toString();
                const QString name = m_pendingPairRequestName;
                m_pendingPairRequestName.clear();
                if (status == QStringLiteral("accepted")) {
                    m_memoryPanel->setSyncStatus(
                        tr("已接受「%1」的配对请求").arg(
                            name.isEmpty() ? tr("设备") : name),
                        true);
                } else if (status == QStringLiteral("rejected")) {
                    m_memoryPanel->setSyncStatus(
                        tr("已拒绝「%1」的配对请求").arg(
                            name.isEmpty() ? tr("设备") : name),
                        true);
                } else if (status == QStringLiteral("expired")) {
                    m_memoryPanel->setSyncStatus(tr("配对请求已过期"));
                } else {
                    m_memoryPanel->setSyncStatus(
                        tr("配对确认失败：%1").arg(
                            status.isEmpty() ? tr("未知响应") : status));
                }
            });
    connect(m_syncController, &SyncController::revoked, this,
            [this](const QString &peerId) {
                if (m_leaveRevoking) {
                    revokeNextPeer();
                    return;
                }
                m_memoryPanel->setSyncStatus(tr("已解绑设备 %1").arg(peerId), true);
                m_syncController->refresh();
            });
    connect(m_syncController, &SyncController::notImplemented, this,
            [this](const QString &feature) {
                if (m_leaveRevoking && feature == QStringLiteral("revoke")) {
                    m_leaveRevoking = false;
                    m_leaveRevokeQueue.clear();
                    m_memoryPanel->setSyncStatus(
                        tr("退出网络失败：解绑接口待后端实现"));
                    m_syncController->refresh();
                    return;
                }
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
                if (m_leaveRevoking) {
                    m_leaveRevoking = false;
                    m_leaveRevokeQueue.clear();
                    m_memoryPanel->setSyncStatus(
                        tr("退出网络失败（%1）：%2").arg(code, message));
                    m_syncController->refresh();
                    return;
                }
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
                if (!m_evidenceDetailDialog) {
                    m_evidenceDetailDialog = new EvidenceDetailDialog();
                }
                m_pendingEvidenceId = evidenceId;
                m_evidenceDetailDialog->showLoading(evidenceId);
                m_transport->evidenceDetail(evidenceId);
            });
    connect(m_transport, &BackendTransport::evidenceDetailResult, this,
            [this](const QJsonObject &evidence) {
                m_pendingEvidenceId.clear();
                if (m_evidenceDetailDialog) {
                    m_evidenceDetailDialog->setEvidence(evidence);
                }
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
                m_lastEvidenceId =
                    response.value(QStringLiteral("evidence_id")).toString();
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
                // 冲突横幅计数 = 审计列表长度（conflictDetected 的 +1 由此重算）。
                m_memoryPanel->setSyncConflictCount(conflicts.size());
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
    // 偏好提取：以最近一次成功写入的 evidence 为输入（POST /preference/extract）。
    connect(m_memoryPanel, &MemoryPanel::extractPreferencesRequested, this,
            [this]() {
                if (m_lastEvidenceId.isEmpty()) {
                    m_memoryPanel->setPreferenceExtractError(
                        tr("尚无已录入的记忆，请先在聊天框录入一条"));
                    return;
                }
                m_preferenceController->extract(
                    QStringList{m_lastEvidenceId});
            });
    connect(m_preferenceController, &PreferenceController::extracted, this,
            [this](int count, int) {
                m_memoryPanel->setPreferenceExtractResult(count);
            });
    connect(m_preferenceController, &PreferenceController::extractFailed, this,
            [this](const QString &code, const QString &message) {
                m_memoryPanel->setPreferenceExtractError(
                    tr("偏好提取失败（%1）：%2").arg(code, message));
            });
    // 偏好列表：GET /preferences，面板打开或手动刷新时拉取。
    connect(m_memoryPanel, &MemoryPanel::preferencesRefreshRequested,
            m_preferenceController, [this]() {
                m_preferenceController->loadList();
            });
    connect(m_preferenceController, &PreferenceController::listLoaded, this,
            [this](const QJsonArray &preferences) {
                m_memoryPanel->setPreferenceList(preferences);
                // B4-3：偏好列表版本对比轻提醒（版本提升/基线后新增）。
                notifyPreferenceChanges(preferences);
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
            [this](const QString &title, const QString &, const QString &,
                   const QString &, const QString &severity) {
                // F3-1：按 severity 分流打扰级别（B3-3 已把 severity 带进
                // conflict_detected 帧，resolution → severity 纯函数映射）：
                //   low    → MERGE 自动合并：静默，仅冲突横幅计数 +1；
                //   medium → NEW_WINS 自动裁决：温和通知（「记忆已更新」）+
                //            角标 +1，不切 Tab、不刷新（无需用户动作，列表在
                //            下次打开面板 / high 刷新时自然更新）；
                //   high / 缺省 / 未知 → MANUAL：现状全动作（「检测到记忆冲突」
                //            + 角标 +1 + 刷新冲突列表 + 面板可见时切冲突 Tab）。
                // 未知/空 severity 经 parseSeverity 一律回落 high：
                // 宁可打扰不漏报（大小写不敏感，见 app/Severity.h）。
                const ui::Severity sev = ui::parseSeverity(severity);
                // 冲突横幅计数 +1（随后 conflictsLoaded 重算为准确值）。
                if (m_memoryPanel) {
                    m_memoryPanel->setSyncConflictCount(
                        m_memoryPanel->syncConflictCount() + 1);
                }
                if (sev == ui::Severity::Low) {
                    return;
                }
                if (m_floatingBall) {
                    m_floatingBall->setUnreadCount(
                        m_floatingBall->unreadCount() + 1);
                }
                if (sev == ui::Severity::Medium) {
                    if (m_notify) {
                        m_notify->notify(tr("记忆已更新"), title);
                    }
                    return;
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
    // 入站配对请求（WS pair_request）：弹确认框，确认/拒绝 → confirmPairing。
    connect(m_eventRouter, &EventRouter::pairingRequested, this,
            [this](const QJsonObject &data) { showPairRequestDialog(data); });
    // 监控捕获事件（WS capture_event）：监控中心打开时实时追加活动记录；
    // sensitive_quarantined 额外弹系统通知（隔离区交互属批次③范围）。
    connect(m_eventRouter, &EventRouter::captureEvent, this,
            [this](const QString &source, const QString &status,
                   const QString &summary, qint64 ts) {
                if (m_monitorCenter && m_monitorCenter->isVisible()) {
                    m_monitorCenter->appendCaptureEvent(source, status,
                                                        summary, ts);
                }
                if (status == QStringLiteral("sensitive_quarantined")
                    && m_notify) {
                    m_notify->notify(tr("监控隔离"), summary);
                }
                // B4-3：目录捕获且已入库时做相关主题轻提醒（每日上限 3）。
                maybeNotifyRelevance(source, status, summary);
            });
    // 聊天窗口可见时视为已读，清除悬浮球角标；同时刷新洞察（欢迎页
    // 动态建议卡每次打开都拿最新数据，在途防重由控制器保证）。
    connect(m_chatWindow, &ChatWindow::shown, this, [this]() {
        if (m_floatingBall) {
            m_floatingBall->clearUnread();
        }
        if (m_deliveryController) {
            m_deliveryController->loadInsights();
        }
    });

    // 远端配置优先：启动拉取 GET /monitor/config；失败保持本地键并标记
    // 非远端权威（离线回退，见 handleMonitorConfigResult / errorOccurred）。
    loadRemoteMonitorConfig();

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
        // 监控中心入口：懒创建的设置对话框只接线一次。
        connect(m_settingsDialog, &SettingsDialog::monitorCenterRequested,
                this, &PixiuApp::openMonitorCenter);
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

void PixiuApp::openMonitorCenter()
{
    if (!m_monitorCenter) {
        m_monitorCenter = new MonitorCenterDialog(m_monitorController);
        // 面板改动 → PUT /monitor/config 上送（选面板信号为唯一触发点，
        // 避免与控制器信号重复上送）；活动记录 Tab 懒加载 → GET /monitor/log。
        connect(m_monitorCenter, &MonitorCenterDialog::configEdited, this,
                &PixiuApp::pushMonitorConfig);
        connect(m_monitorCenter, &MonitorCenterDialog::logPageRequested, this,
                [this](int limit, int offset) {
                    if (m_transport) {
                        m_transport->monitorLog(limit, offset);
                    }
                });
        // 配置拉取/上送失败可能发生在面板创建之前——创建时按远端权威
        // 标记（且无在途请求，避免「GET 尚未返回」的瞬态误报）初始化
        // 离线提示，保证「失败发生在面板创建前」后面板打开即有提示。
        m_monitorCenter->setOfflineHint(!m_monitorRemoteAuthoritative
                                        && !m_monitorConfigPending);
    }
    m_monitorCenter->showAndFocus();
}

void PixiuApp::refreshMonitorUi()
{
    if (!m_monitorController) {
        return;
    }
    const bool on = m_monitorController->isEnabled();
    if (m_chatWindow) {
        // 「⏸ 已暂停」徽标仅对曾开启过监控的用户有意义：开启中或从未启用
        // 过（默认关闭）都不显示，避免新用户常驻看到暂停提示而困惑。
        m_chatWindow->setMonitorActive(
            on || !m_monitorController->hasEverBeenEnabled());
    }
    const QString pauseText = on ? tr("暂停监控") : tr("继续监控");
    if (m_tray) {
        m_tray->setPauseActionText(pauseText);
    }
    if (m_floatingBall) {
        m_floatingBall->setPauseMenuText(pauseText);
    }
}

void PixiuApp::loadRemoteMonitorConfig()
{
    if (!m_transport) {
        return;
    }
    m_monitorConfigPending = true;
    m_transport->monitorConfig();
}

void PixiuApp::handleMonitorConfigResult(const QJsonObject &config)
{
    m_monitorConfigPending = false;
    if (!m_monitorController) {
        return;
    }
    if (!m_monitorPendingPutPayload.isEmpty()) {
        // 暂存载荷非空 = 在途 PUT（或与在途 PUT 竞争的 GET 响应）：
        // 回声校验——仅当响应与暂存载荷一致才整体应用；乱序旧回声/
        // 过时 GET 不覆盖用户最新改动，不匹配则跳过应用、保留暂存
        // 等待匹配回声。
        const bool echoMatches =
            config.value(QStringLiteral("enabled"))
                == m_monitorPendingPutPayload.value(QStringLiteral("enabled"))
            && config.value(QStringLiteral("sources"))
                == m_monitorPendingPutPayload.value(QStringLiteral("sources"))
            && config.value(QStringLiteral("directories"))
                == m_monitorPendingPutPayload.value(
                    QStringLiteral("directories"));
        if (echoMatches) {
            applyMonitorConfig(config);
            m_monitorPendingPutPayload = QJsonObject();
            // 用户改动已确认上送：读后写竞态窗口关闭，后续 GET 可正常应用。
            m_monitorConfigDirty = false;
        }
        return;
    }
    // 无暂存载荷 = 启动/断线恢复拉取（GET）响应：仅当用户尚未改动面板
    // 时应用（用户本地改动优先）；已改动则跳过应用，仅更新远端权威标记。
    if (m_monitorConfigDirty) {
        m_monitorRemoteAuthoritative = true;
        return;
    }
    applyMonitorConfig(config);
}

void PixiuApp::handleMonitorLogResult(const QJsonArray &events)
{
    if (m_monitorCenter) {
        m_monitorCenter->appendRemoteLog(events);
    }
}

void PixiuApp::pushMonitorConfig()
{
    if (!m_transport || !m_monitorController) {
        return;
    }
    // 用户本地改动优先于尚未到达的 GET 响应（读后写竞态防护，
    // handleMonitorConfigResult 据此跳过过时 GET 的应用）。
    m_monitorConfigDirty = true;
    // 去抖：连发改动合并为一次 PUT——定时器 pending 时只更新暂存载荷，
    // 减少并发 PUT；定时器触发时以最新暂存载荷发出。
    m_monitorPendingPutPayload = buildMonitorConfigPayload();
    if (!m_configPushTimer) {
        m_configPushTimer = new QTimer(this);
        m_configPushTimer->setSingleShot(true);
        m_configPushTimer->setInterval(300);
        connect(m_configPushTimer, &QTimer::timeout, this, [this]() {
            if (m_transport && !m_monitorPendingPutPayload.isEmpty()) {
                m_monitorConfigPending = true;
                m_transport->updateMonitorConfig(m_monitorPendingPutPayload);
            }
        });
    }
    if (!m_configPushTimer->isActive()) {
        m_configPushTimer->start();
    }
}

QJsonObject PixiuApp::buildMonitorConfigPayload() const
{
    // 全量提交（契约要求，不做局部 patch）：形状与 GET 响应一致。
    QJsonObject sources;
    for (int i = 0; i < MonitorController::sourceCount(); ++i) {
        const auto source = static_cast<MonitorSource>(i);
        sources.insert(MonitorController::sourceKey(source),
                       m_monitorController->isSourceEnabled(source));
    }
    QJsonArray dirs;
    for (const QString &dir : m_monitorController->directories()) {
        dirs.append(dir);
    }
    QJsonObject payload;
    payload.insert(QStringLiteral("enabled"),
                   m_monitorController->isEnabled());
    payload.insert(QStringLiteral("sources"), sources);
    payload.insert(QStringLiteral("directories"), dirs);
    return payload;
}

void PixiuApp::applyMonitorConfig(const QJsonObject &config)
{
    if (!m_monitorController) {
        return;
    }
    // 远端配置优先：覆盖控制器状态（enabled / 四数据源 / 目录）。
    // 控制器 set* 同步落盘本地键，作为离线回退缓存。
    m_monitorController->setEnabled(
        config.value(QStringLiteral("enabled")).toBool(false));
    const QJsonObject sources =
        config.value(QStringLiteral("sources")).toObject();
    for (int i = 0; i < MonitorController::sourceCount(); ++i) {
        const auto source = static_cast<MonitorSource>(i);
        m_monitorController->setSourceEnabled(
            source, sources.value(MonitorController::sourceKey(source))
                        .toBool(false));
    }
    QStringList dirs;
    const QJsonArray dirArray =
        config.value(QStringLiteral("directories")).toArray();
    for (const QJsonValue &value : dirArray) {
        dirs << value.toString();
    }
    m_monitorController->setDirectories(dirs);
    m_monitorRemoteAuthoritative = true;
    // 面板已打开时清除离线提示（远端已恢复同步）。
    if (m_monitorCenter) {
        m_monitorCenter->setOfflineHint(false);
    }
}

void PixiuApp::maybeNotifyRelevance(const QString &source, const QString &status,
                                    const QString &summary)
{
    // 仅目录捕获且已入库（ingested）参与相关主题判断：敏感隔离/忽略/剪贴板
    // 内容不打扰（隔离另有「监控隔离」通知，且敏感条目不应被回显）。
    if (source != QStringLiteral("directory")
        || status != QStringLiteral("ingested")
        || !m_notify || m_deliveryInsights.isEmpty()) {
        return;
    }
    // 目录捕获 summary 形如「记住文件 NAME」，取 NAME 作为文件名（展示与
    // token 化均用文件名；前缀 token 对命中无贡献，反而会污染展示文案）。
    QString fileName = summary;
    const QString prefix = QStringLiteral("记住文件 ");
    if (fileName.startsWith(prefix)) {
        fileName = fileName.mid(prefix.size()).trimmed();
    }
    if (fileName.isEmpty()) {
        return;
    }
    // 每日上限：跨日复位（轻提醒避免刷屏打扰）。
    const QDate today = QDate::currentDate();
    if (m_relevanceReminderDay != today) {
        m_relevanceReminderDay = today;
        m_relevanceReminderCount = 0;
    }
    if (m_relevanceReminderCount >= kRelevanceReminderDailyCap) {
        return;
    }
    // 文件名 token vs 近期洞察 title token 交集（按 score 降序返回，取首个命中）。
    const QSet<QString> fileTokens = tokenizeForRelevance(fileName);
    for (const QJsonValue &value : m_deliveryInsights) {
        const QJsonObject obj = value.toObject();
        const QString title = obj.value(QStringLiteral("title")).toString();
        if (title.trimmed().isEmpty()) {
            continue;
        }
        const QSet<QString> titleTokens = tokenizeForRelevance(title);
        bool related = false;
        for (const QString &ft : fileTokens) {
            for (const QString &tt : titleTokens) {
                if (tokensRelated(ft, tt)) {
                    related = true;
                    break;
                }
            }
            if (related) {
                break;
            }
        }
        if (related) {
            ++m_relevanceReminderCount;
            m_notify->notify(tr("相关主题提醒"),
                             tr("已记住 文件 %1（与您近期的 %2 相关）")
                                 .arg(fileName, title));
            return;
        }
    }
}

void PixiuApp::notifyPreferenceChanges(const QJsonArray &preferences)
{
    if (!m_notify) {
        return;
    }
    // 偏好提醒无每日上限（spec 节制原则仅点名相关性提醒/目录事件两类提醒）：
    // 豁免理由——偏好变更低频（设置面板手动触发，非事件流）+ 首载只建基线
    // 不提醒 + 版本未变不重复提醒，通知量天然受控，无需再叠加上限。
    QHash<QString, int> seen;
    for (const QJsonValue &value : preferences) {
        const QJsonObject obj = value.toObject();
        const QString key = obj.value(QStringLiteral("key")).toString();
        if (key.trimmed().isEmpty()) {
            continue;
        }
        const int version = obj.value(QStringLiteral("version")).toInt(0);
        seen.insert(key, version);
        // 首次列表只建基线（避免首次打开面板时的通知风暴）；此后版本提升或
        // 基线后新增偏好才轻提醒，版本未变不重复提醒（不误报）。
        if (!m_prefBaselineEstablished) {
            continue;
        }
        const auto it = m_prefVersions.constFind(key);
        if (it == m_prefVersions.constEnd()) {
            m_notify->notify(tr("偏好提醒"),
                             tr("已学习您的偏好：%1").arg(key));
        } else if (version > it.value()) {
            m_notify->notify(tr("偏好提醒"),
                             tr("已学习您的偏好：%1").arg(key));
        }
    }
    m_prefVersions = seen;
    m_prefBaselineEstablished = true;
}

void PixiuApp::handleBackendEvent(const QJsonObject &event)
{
    // 语义分发交由 EventRouter；未知/畸形事件在路由层安全忽略。
    if (m_eventRouter) {
        m_eventRouter->handleEvent(event);
    }
}

void PixiuApp::showPairRequestDialog(const QJsonObject &data)
{
    const QString requestId = data.value(QStringLiteral("request_id")).toString();
    if (requestId.trimmed().isEmpty()) {
        qCWarning(lcApp) << "ignoring pair_request without request_id";
        return;
    }
    m_pendingPairRequestId = requestId;
    const QString fromName = data.value(QStringLiteral("from_name")).toString();
    const QString fromDevice = data.value(QStringLiteral("from_device_id")).toString();
    m_pendingPairRequestName = fromName.isEmpty() ? fromDevice : fromName;
    const QString pin = data.value(QStringLiteral("pin")).toString();

    if (!m_pairRequestDialog) {
        // 轻量确认框（挂在主窗口下，随窗口生命周期释放）。
        m_pairRequestDialog = new QDialog(m_chatWindow);
        m_pairRequestDialog->setObjectName(QStringLiteral("pairRequestDialog"));
        m_pairRequestDialog->setWindowTitle(tr("配对请求"));
        m_pairRequestDialog->setMinimumWidth(280);

        m_pairRequestInfoLabel = new QLabel(m_pairRequestDialog);
        m_pairRequestInfoLabel->setObjectName(QStringLiteral("pairRequestInfoLabel"));
        m_pairRequestInfoLabel->setWordWrap(true);

        m_pairRequestPinLabel = new QLabel(m_pairRequestDialog);
        m_pairRequestPinLabel->setObjectName(QStringLiteral("pairRequestPinLabel"));
        m_pairRequestPinLabel->setFont(ui::Font::title());
        m_pairRequestPinLabel->setTextInteractionFlags(Qt::TextSelectableByMouse);

        QPushButton *rejectButton = new QPushButton(tr("拒绝"), m_pairRequestDialog);
        rejectButton->setObjectName(QStringLiteral("pairRequestRejectButton"));
        rejectButton->setAccessibleName(tr("拒绝配对请求"));
        rejectButton->setCursor(Qt::PointingHandCursor);
        QPushButton *acceptButton = new QPushButton(tr("确认"), m_pairRequestDialog);
        acceptButton->setObjectName(QStringLiteral("pairRequestAcceptButton"));
        acceptButton->setAccessibleName(tr("确认配对"));
        acceptButton->setStyleSheet(ui::accentButtonStyle());
        acceptButton->setCursor(Qt::PointingHandCursor);
        // 未知来源请求默认聚焦「拒绝」，避免误触确认。
        rejectButton->setDefault(true);

        connect(rejectButton, &QPushButton::clicked, this, [this]() {
            const QString id = m_pendingPairRequestId;
            m_pendingPairRequestId.clear();
            if (!id.isEmpty() && m_syncController) {
                m_syncController->confirmPairing(id, false);
            }
            if (m_pairRequestDialog) {
                m_pairRequestDialog->hide();
            }
        });
        connect(acceptButton, &QPushButton::clicked, this, [this]() {
            const QString id = m_pendingPairRequestId;
            m_pendingPairRequestId.clear();
            if (!id.isEmpty() && m_syncController) {
                m_syncController->confirmPairing(id, true);
            }
            if (m_pairRequestDialog) {
                m_pairRequestDialog->hide();
            }
        });

        QHBoxLayout *buttonRow = new QHBoxLayout();
        buttonRow->addStretch(1);
        buttonRow->addWidget(rejectButton);
        buttonRow->addWidget(acceptButton);

        QVBoxLayout *layout = new QVBoxLayout(m_pairRequestDialog);
        layout->addWidget(m_pairRequestInfoLabel);
        layout->addWidget(m_pairRequestPinLabel);
        layout->addLayout(buttonRow);
    }

    m_pairRequestInfoLabel->setText(
        tr("来自「%1」的配对请求").arg(m_pendingPairRequestName));
    m_pairRequestPinLabel->setText(
        pin.isEmpty() ? tr("PIN：未知") : tr("PIN：%1").arg(pin));
    m_pairRequestDialog->show();
    m_pairRequestDialog->raise();
    m_pairRequestDialog->activateWindow();
}

void PixiuApp::startLeaveNetwork()
{
    if (m_leaveRevoking) {
        return;
    }
    m_leaveRevokeQueue.clear();
    for (const QJsonValue &value : m_syncPeers) {
        const QJsonObject peer = value.toObject();
        if (peer.value(QStringLiteral("is_self")).toBool(false)) {
            continue;
        }
        const QString id = peer.value(QStringLiteral("id")).toString();
        if (!id.trimmed().isEmpty()) {
            m_leaveRevokeQueue.append(id);
        }
    }
    if (m_leaveRevokeQueue.isEmpty()) {
        m_memoryPanel->setSyncStatus(tr("无可退出的节点"));
        return;
    }
    m_leaveRevoking = true;
    m_memoryPanel->setSyncStatus(tr("正在退出同步网络…"));
    revokeNextPeer();
}

void PixiuApp::revokeNextPeer()
{
    // SyncController.revokePeer 一次仅一台在途：串行推进，等待 revoked/
    // failed/notImplemented 后再发下一台。
    while (!m_leaveRevokeQueue.isEmpty()) {
        const QString id = m_leaveRevokeQueue.takeFirst();
        if (id.trimmed().isEmpty()) {
            continue;
        }
        m_syncController->revokePeer(id);
        return;
    }
    finishLeaveNetwork();
}

void PixiuApp::finishLeaveNetwork()
{
    m_leaveRevoking = false;
    m_leaveRevokeQueue.clear();
    m_memoryPanel->setSyncStatus(tr("已退出同步网络"), true);
    // 完成后刷新：节点列表回落到本机，摘要反映退出后状态。
    m_syncController->refresh();
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
