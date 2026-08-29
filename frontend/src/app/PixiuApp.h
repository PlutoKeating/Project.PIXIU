#ifndef PIXIU_APP_H
#define PIXIU_APP_H

#include <QJsonArray>
#include <QJsonObject>
#include <QObject>
#include <QScopedPointer>
#include <QStringList>

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
class MonitorController;
class MonitorCenterDialog;
class QTimer;
class QDialog;
class QLabel;

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

    // 测试注入：替换默认 HTTP transport（仅测试用，须在 start() 前调用）。
    void setTransportForTest(BackendTransport *transport);

    // 测试注入：替换默认桌面通知服务（仅测试用，须在 start() 前调用；
    // 与 setTransportForTest 同模式，start() 检测到已注入则不再创建默认实例）。
    void setNotifyServiceForTest(NotifyService *service);

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
    // 监控掌控层：状态单一事实来源 + 监控中心面板（懒创建）。
    MonitorController *m_monitorController = nullptr;
    MonitorCenterDialog *m_monitorCenter = nullptr;
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
    // 监控配置远端权威标记：true=远端配置已成功拉取/上送；
    // false=仅本地键生效（离线回退，状态行提示「离线，仅本地生效」）。
    bool m_monitorRemoteAuthoritative = false;
    // 监控配置请求（启动 GET / 面板 PUT）在途标记：失败路由到面板离线提示。
    bool m_monitorConfigPending = false;
    // 暂存待确认的 PUT 载荷（回声校验：仅当响应与暂存载荷一致才整体应用，
    // 防乱序旧回声/过时 GET 覆盖用户最新改动）。空对象 = 无在途 PUT。
    QJsonObject m_monitorPendingPutPayload;
    // 用户是否已改动面板（configEdited 发射时置 true；匹配回声应用后
    // 复位）。GET 响应到达时若为 true 则跳过应用（用户本地改动优先）。
    bool m_monitorConfigDirty = false;
    // configEdited → PUT 的去抖定时器（合并连发，减少并发 PUT；
    // 定时器 pending 时只更新暂存载荷）。
    QTimer *m_configPushTimer = nullptr;
    // 入站配对请求确认对话框（WS pair_request → 确认/拒绝）与在途请求。
    QDialog *m_pairRequestDialog = nullptr;
    QLabel *m_pairRequestInfoLabel = nullptr;
    QLabel *m_pairRequestPinLabel = nullptr;
    QString m_pendingPairRequestId;
    QString m_pendingPairRequestName;
    // 最近一次节点列表（退出网络批处理队列来源）。
    QJsonArray m_syncPeers;
    // 退出网络批处理：逐台 revoke 队列（SyncController.revokePeer 一次一台，
    // 串行等待 revoked 后再发下一台；完成后 refresh）。
    QStringList m_leaveRevokeQueue;
    bool m_leaveRevoking = false;
    struct Private;
    QScopedPointer<Private> d;

private:
    void toggleChatWindow();
    void openSettings();
    void openMonitorCenter();
    void refreshMonitorUi();
    void handleBackendEvent(const QJsonObject &event);
    // 远端监控配置（A-3）：启动拉取 / 回包应用 / 面板改动上送。
    void loadRemoteMonitorConfig();
    void handleMonitorConfigResult(const QJsonObject &config);
    void handleMonitorLogResult(const QJsonArray &events);
    void pushMonitorConfig();
    // 构建全量 PUT 载荷（与 GET 响应同形状：enabled/sources/directories）。
    QJsonObject buildMonitorConfigPayload() const;
    // 将远端配置整体应用到控制器（enabled / 四数据源 / 目录）+ 置远端
    // 权威标记 + 清除面板离线提示。
    void applyMonitorConfig(const QJsonObject &config);
    // SN-6：WS pair_request 帧 → 配对确认对话框（展示设备名 + PIN）。
    void showPairRequestDialog(const QJsonObject &data);
    // SN-6：退出网络批处理（逐台 revoke，串行推进）。
    void startLeaveNetwork();
    void revokeNextPeer();
    void finishLeaveNetwork();
};

#endif // PIXIU_APP_H
