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
    struct Private;
    QScopedPointer<Private> d;

private:
    void toggleChatWindow();
    void handleBackendEvent(const QJsonObject &event);
};

#endif // PIXIU_APP_H
