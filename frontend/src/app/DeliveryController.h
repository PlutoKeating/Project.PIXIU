#ifndef PIXIU_DELIVERY_CONTROLLER_H
#define PIXIU_DELIVERY_CONTROLLER_H

#include <QJsonArray>
#include <QJsonObject>
#include <QObject>

class BackendTransport;

// 递送层控制器（批次④ B4-3）：封装 /delivery/insights（欢迎页动态建议）与
// /delivery/digest（今日简报）的请求与结果上抛（仿 SyncController 模式）。
//
// 契约语义（docs/API.md §3.23-3.24）：
//   - GET /delivery/insights 返回 {"insights": [...]}；空数组是空库/runtime
//     未启动的合法空态（非错误、非 not_implemented 占位），原样透传，由
//     ChatWindow 保留静态建议兜底；
//   - GET /delivery/digest 返回 {"date","summary"}；
//   - 网络/HTTP/API 错误走 failed，不伪造成功。
class DeliveryController : public QObject
{
    Q_OBJECT

public:
    explicit DeliveryController(BackendTransport *transport, QObject *parent = nullptr);

    // 拉取洞察（幂等；对应在途请求未返回时忽略重复调用）。
    void loadInsights();

    // 拉取今日简报（幂等；在途时忽略重复调用）。
    void loadDigest();

signals:
    // 洞察就绪（含合法空数组）。
    void insightsLoaded(const QJsonArray &insights);
    // 今日简报就绪（date/summary）。
    void digestLoaded(const QJsonObject &response);
    // 洞察/简报请求失败（NETWORK_ERROR / HTTP 错误码等）。
    void failed(const QString &code, const QString &message);

private:
    BackendTransport *m_transport = nullptr;
    bool m_insightsPending = false;
    bool m_digestPending = false;
};

#endif // PIXIU_DELIVERY_CONTROLLER_H
