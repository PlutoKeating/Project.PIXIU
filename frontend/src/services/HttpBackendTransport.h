#ifndef PIXIU_HTTP_BACKEND_TRANSPORT_H
#define PIXIU_HTTP_BACKEND_TRANSPORT_H

#include <QJsonObject>
#include <QString>
#include <QPointer>
#include <functional>

#include "services/BackendTransport.h"

class QNetworkAccessManager;
class QNetworkReply;
class QTimer;
class QUrl;

// HTTP/JSON 后端传输：对齐 docs/API.md 的公共 REST 契约。
//
// 行为约定：
//   - 异步请求，结果/错误经信号返回，UI 线程永不阻塞；
//   - 后端地址取环境变量 PIXIU_BACKEND_URL，默认 http://127.0.0.1:8765；
//   - JSON 解析容忍未知字段；错误按 API 错误码或 NETWORK_ERROR/TIMEOUT 上报；
//   - 显式连接时由 /health 判定就绪；普通请求不覆盖该判定。
//   - 未启用探测时 Connected 仅表示业务 HTTP 可达，不代表 SDK/版本兼容。
class HttpBackendTransport : public BackendTransport
{
    Q_OBJECT

public:
    // healthProbeIntervalMs：周期健康探测间隔（默认 10s，测试可注入更短间隔）。
    explicit HttpBackendTransport(QObject *parent = nullptr,
                                  int healthProbeIntervalMs = 10000);

    void connectToBackend() override;
    void disconnectFromBackend() override;

    quint64 queryMemory(const QString &text, const QJsonObject &contextHint) override;
    void writeMemory(const QJsonObject &payload) override;
    void memoryContext(const QJsonObject &payload) override;
    void updateMemory(const QJsonObject &payload) override;
    void memoryItem(const QString &knowledgeId, const QString &scope) override;
    void reviewedForget(const QJsonObject &payload) override;
    void listConflicts() override;
    void preferenceHistory(const QString &preferenceId) override;
    void extractPreferences(const QJsonObject &payload) override;
    void preferencesList(const QString &scope) override;
    void evidenceDetail(const QString &evidenceId) override;
    void createPairingToken(const QJsonObject &payload) override;
    void monitorConfig() override;
    void updateMonitorConfig(const QJsonObject &payload) override;
    void monitorLog(int limit, int offset) override;
    void promoteMemory(const QJsonObject &payload) override;
    void pairDevice(const QJsonObject &payload) override;
    void listPeers() override;
    void syncStatus() override;
    void revokePeer(const QString &peerId) override;
    void discoverDevices() override;
    void requestPairing(const QString &targetId) override;
    void confirmPairing(const QString &requestId, bool accept) override;
    void updateSyncSettings(bool enabled, bool paused) override;
    void deliveryInsights() override;
    void deliveryDigest(const QString &date = QString()) override;
    void backendDiagnostics() override;

    void recognizeImage(const QJsonObject &payload);
    void reviewConflict(const QString &id);
    void resolveConflict(const QString &id, const QJsonObject &payload);
    void flowContexts(const QString &scope);
    void agentMemorySettings();
    void saveAgentMemorySettings(const QJsonObject &payload);

    ConnectionState connectionState() const override;

    // 后端基础地址（测试/诊断用）。
    QString baseUrl() const override;

signals:
    void imageRecognized(const QJsonObject &result);
    void conflictReviewResult(const QJsonObject &review);
    void conflictResolved(const QJsonObject &result);
    void flowContextsResult(const QJsonObject &contexts);
    void agentMemorySettingsResult(const QJsonObject &settings);

private:
    QUrl endpoint(const QString &path) const;

    // 周期健康探测：GET /health，校验组件与数据库就绪，不广播业务信号。
    // 用于后端中途挂掉/事后恢复时顶栏状态与离线引导能及时刷新。
    void probeHealth();

    void getJson(const QString &path,
                 const std::function<void(quint64, const QJsonObject &)> &onSuccess,
                 quint64 tag = 0);
    void postJson(const QString &path,
                  const QJsonObject &body,
                  const std::function<void(quint64, const QJsonObject &)> &onSuccess,
                  quint64 tag = 0);
    // PUT 语义助手：与 postJson 对称，4xx/5xx 与传输错误统一走 handleReply。
    void putJson(const QString &path,
                 const QJsonObject &body,
                 const std::function<void(quint64, const QJsonObject &)> &onSuccess,
                 quint64 tag = 0);

    void handleReply(QNetworkReply *reply,
                     const std::function<void(quint64, const QJsonObject &)> &onSuccess,
                     const QString &fallbackErrorCode,
                     quint64 tag);
    void setConnectionState(ConnectionState state);

    QNetworkAccessManager *m_network = nullptr;
    QString m_baseUrl;
    ConnectionState m_state = ConnectionState::Disconnected;
    QTimer *m_healthTimer = nullptr;
    QPointer<QNetworkReply> m_healthReply;
    quint64 m_connectionGeneration = 0;
    quint64 m_nextRequestId = 1;
};

#endif // PIXIU_HTTP_BACKEND_TRANSPORT_H
