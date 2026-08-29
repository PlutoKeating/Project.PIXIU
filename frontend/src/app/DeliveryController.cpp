#include "app/DeliveryController.h"

#include <QLoggingCategory>

#include "services/BackendTransport.h"

Q_LOGGING_CATEGORY(lcDelivery, "pixiu.delivery")

DeliveryController::DeliveryController(BackendTransport *transport, QObject *parent)
    : QObject(parent)
    , m_transport(transport)
{
    connect(m_transport, &BackendTransport::insightsResult, this,
            [this](const QJsonArray &insights) {
                if (!m_insightsPending) {
                    return; // 无在途请求，忽略过期响应
                }
                m_insightsPending = false;
                // 空数组是合法空态（空库/未启动），原样透传。
                emit insightsLoaded(insights);
            });
    connect(m_transport, &BackendTransport::digestResult, this,
            [this](const QJsonObject &response) {
                if (!m_digestPending) {
                    return; // 无在途请求，忽略过期响应
                }
                m_digestPending = false;
                emit digestLoaded(response);
            });
    connect(m_transport, &BackendTransport::errorOccurred, this,
            [this](const QString &code, const QString &message, const QString &) {
                // 通用错误通道：仅处理递送相关的在途请求；失败清空在途标记，
                // 避免残留 pending 卡死后续请求。
                // 全量清理语义（设计债）：errorOccurred 不携带请求身份（第三
                // 个参数 requestId 未与在途请求关联），任一应用级错误（含无关
                // 端点的失败）都会清空全部递送 pending——随后真响应到达时会被
                // 各自的 stale 检查丢弃（insights/digest 的「无在途请求」分支）。
                // 与 SyncController 既有模式一致：递送请求互斥、不并发，all-or-
                // nothing 清理的代价可接受；长期修复方向是给在途请求关联
                // requestId，按请求身份定位失败并仅清理对应 pending（不改行为）。
                if (!m_insightsPending && !m_digestPending) {
                    return;
                }
                m_insightsPending = false;
                m_digestPending = false;
                emit failed(code, message);
            });
}

void DeliveryController::loadInsights()
{
    if (m_insightsPending) {
        return; // 在途防重
    }
    m_insightsPending = true;
    qCInfo(lcDelivery) << "loading insights";
    m_transport->deliveryInsights();
}

void DeliveryController::loadDigest()
{
    if (m_digestPending) {
        return; // 在途防重
    }
    m_digestPending = true;
    qCInfo(lcDelivery) << "loading digest";
    m_transport->deliveryDigest();
}
