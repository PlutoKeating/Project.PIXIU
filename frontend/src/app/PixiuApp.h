#ifndef PIXIU_APP_H
#define PIXIU_APP_H

#include <QJsonObject>
#include <QObject>
#include <QScopedPointer>

class SingleInstanceGuard;
class TrayIcon;
class AppSettings;
class FloatingBall;
class ChatWindow;
class ShortcutManager;
class BackendTransport;
class QueryController;
class WriteController;
class ImportDialog;
class WebSocketClient;
class NotifyService;
class ForgetController;
class ForgetDialog;
class SettingsDialog;
class MemoryPanel;
class EvidenceDetailDialog;
class ConflictController;
class PreferenceController;
class ThemeService;
class SyncController;
class EventRouter;

// PixiuApp 是整个前端应用的生命周期所有者。
//
// Phase 1B 职责边界：
//   - 创建应用对象、统一启动与退出流程；
//   - 作为后续顶层服务（MemoryClient/SyncClient/NotifyService/ThemeService）与
//     窗口（FloatingBall/ChatWindow/MemoryPanel）的挂载点；
//   - 明确 QObject 所有权边界：所有子对象均以 PixiuApp 为 parent。
//
// 本类不包含：单实例守护、系统托盘、设置持久化、网络或 KylinSDK 集成
// （这些分别属于后续独立 feature）。
class PixiuApp : public QObject
{
    Q_OBJECT

public:
    explicit PixiuApp(QObject *parent = nullptr);
    ~PixiuApp() override;

    // 启动应用：初始化核心服务与窗口挂载点。失败时返回 false。
    bool start();

    // 退出前清理：停止异步任务、断开连接并释放资源。
    void shutdown();

signals:
    // 生命周期信号，供后续服务与窗口订阅。
    void started();
    void aboutToShutdown();

private:
    SingleInstanceGuard *m_instanceGuard = nullptr;
    TrayIcon *m_tray = nullptr;
    AppSettings *m_settings = nullptr;
    FloatingBall *m_floatingBall = nullptr;
    ChatWindow *m_chatWindow = nullptr;
    ShortcutManager *m_shortcutManager = nullptr;
    BackendTransport *m_transport = nullptr;
    QueryController *m_queryController = nullptr;
    WriteController *m_writeController = nullptr;
    ImportDialog *m_importDialog = nullptr;
    WebSocketClient *m_wsClient = nullptr;
    NotifyService *m_notify = nullptr;
    ForgetController *m_forgetController = nullptr;
    ForgetDialog *m_forgetDialog = nullptr;
    SettingsDialog *m_settingsDialog = nullptr;
    MemoryPanel *m_memoryPanel = nullptr;
    EvidenceDetailDialog *m_evidenceDetailDialog = nullptr;
    ConflictController *m_conflictController = nullptr;
    PreferenceController *m_preferenceController = nullptr;
    SyncController *m_syncController = nullptr;
    EventRouter *m_eventRouter = nullptr;
    ThemeService *m_themeService = nullptr;
    // 配对请求在途标记：仅将配对相关错误路由到同步 Tab 状态行，
    // 避免与其他端点（写入/遗忘/冲突/偏好）的通用错误互相干扰。
    bool m_pairPending = false;
    // 配对令牌生成在途标记：错误路由到配对对话框。
    bool m_tokenPending = false;
    // WS forget_confirmation 事件携带的待确认指令（确认后执行第二阶段）。
    QString m_remoteForgetCommand;
    // 最近一次偏好历史请求的 ID（失败重试时重发）。
    QString m_lastPreferenceId;
    // 最近一次证据详情请求的 ID（响应路由与错误上报用）。
    QString m_pendingEvidenceId;
    // 最近一次成功写入返回的 evidence_id（偏好提取输入源）。
    QString m_lastEvidenceId;
    // 后端离线引导提示是否已展示（每次断线仅提示一次，恢复后复位）。
    bool m_offlineGuidanceShown = false;
    struct Private;
    QScopedPointer<Private> d;

private:
    void toggleChatWindow();
    void openSettings();
    void handleBackendEvent(const QJsonObject &event);
};

#endif // PIXIU_APP_H
