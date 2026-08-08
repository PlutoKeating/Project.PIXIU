#ifndef PIXIU_HTTP_BACKEND_TRANSPORT_H
#define PIXIU_HTTP_BACKEND_TRANSPORT_H

#include <QJsonObject>
#include <QString>
#include <functional>

#include "services/BackendTransport.h"

class QNetworkAccessManager;
class QNetworkReply;
class QUrl;

// HTTP/JSON 后端传输：对齐 docs/API.md 的 12 个 REST 端点。
//
// 行为约定：
//   - 异步请求，结果/错误经信号返回，UI 线程永不阻塞；
//   - 后端地址取环境变量 PIXIU_BACKEND_URL，默认 http://127.0.0.1:8765；
//   - JSON 解析容忍未知字段；错误按 API 错误码或 NETWORK_ERROR/TIMEOUT 上报；
//   - 每次成功请求后连接状态置为 Connected，网络失败置为 Error。
class HttpBackendTransport : public BackendTransport
{
    Q_OBJECT

public:
    explicit HttpBackendTransport(QObject *parent = nullptr);

    void connectToBackend() override;
    void disconnectFromBackend() override;

    quint64 queryMemory(const QString &text, const QJsonObject &contextHint) override;
    void writeMemory(const QJsonObject &payload) override;
    void forget(const QString &command, bool confirm) override;
    void listConflicts() override;
    void preferenceHistory(const QString &preferenceId) override;
    void promoteMemory(const QJsonObject &payload) override;
    void pairDevice(const QJsonObject &payload) override;
    void listPeers() override;
    void syncStatus() override;
    void revokePeer(const QString &peerId) override;

    ConnectionState connectionState() const override;

    // 后端基础地址（测试/诊断用）。
    QString baseUrl() const override;

private:
    QUrl endpoint(const QString &path) const;

    void getJson(const QString &path,
                 const std::function<void(quint64, const QJsonObject &)> &onSuccess,
                 quint64 tag = 0);
    void postJson(const QString &path,
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
    quint64 m_nextRequestId = 1;
};

#endif // PIXIU_HTTP_BACKEND_TRANSPORT_H
