#include "ServiceStatusPage.h"
#include "services/HttpBackendTransport.h"
#include <QDateTime>
#include <QLabel>
#include <QPlainTextEdit>
#include <QPushButton>
#include <QRegularExpression>
#include <QVBoxLayout>

namespace pixiu {
ServiceStatusPage::ServiceStatusPage(QWidget *parent, BackendTransport *transport) : QWidget(parent)
{
    setObjectName("serviceStatusPage");
    auto *http = transport ? transport : new HttpBackendTransport(this);
    auto *layout = new QVBoxLayout(this);
    auto *intro = new QLabel(tr("读取记忆后端的健康、版本和实际适配器。三个接口依次读取，不是持续监控或原子快照；不调用模型，不修改配置。能力报告不能代替真实操作、性能或完整验收。"), this);
    intro->setWordWrap(true);
    layout->addWidget(intro);
    auto *refresh = new QPushButton(tr("读取服务与能力"), this);
    refresh->setObjectName("serviceRefresh");
    layout->addWidget(refresh);
    auto *status = new QLabel(tr("尚未读取。"), this);
    status->setObjectName("serviceStatus");
    status->setTextFormat(Qt::PlainText);
    status->setWordWrap(true);
    layout->addWidget(status);
    auto *details = new QPlainTextEdit(this);
    details->setObjectName("serviceDetails");
    details->setAccessibleName(tr("后端版本与运行能力"));
    details->setReadOnly(true);
    layout->addWidget(details, 1);
    connect(refresh, &QPushButton::clicked, this, [=]() {
        if (m_pending) return;
        m_pending = true;
        details->clear();
        status->setText(tr("正在读取服务状态…"));
        refresh->setEnabled(false);
        http->backendDiagnostics();
    });
    connect(http, &BackendTransport::errorOccurred, this,
        [=](const QString &code, const QString &, const QString &) {
        if (!m_pending) return;
        m_pending = false;
        refresh->setEnabled(true);
        details->clear();
        // Do not repeat endpoint URLs or credential-bearing server error text.
        const auto safeCode = QRegularExpression(QStringLiteral("^[A-Z0-9_]{1,64}$")).match(code).hasMatch()
            ? code : QStringLiteral("UNKNOWN_ERROR");
        status->setText(tr("读取失败（%1）。未确认服务就绪，可重试。").arg(safeCode));
    });
    connect(http, &BackendTransport::diagnosticsResult, this, [=](const QJsonObject &report) {
        if (!m_pending) return;
        m_pending = false;
        refresh->setEnabled(true);
        const auto health = report.value("health").toObject();
        const auto version = report.value("version").toObject();
        const auto caps = report.value("capabilities").toObject();
        const auto platform = caps.value("platform").toObject();
        const auto embedding = caps.value("embedding").toObject();
        const auto vector = caps.value("vector_store").toObject();
        const auto text = [](const QJsonObject &obj, const char *key) {
            return obj.value(key).isString() && !obj.value(key).toString().isEmpty();
        };
        const auto adapter = [&](const QJsonObject &obj) {
            return text(obj, "configured") && text(obj, "runtime") && obj.value("compliant").isBool()
                && obj.value("compliant").toBool() == (obj.value("runtime").toString() == "kylin");
        };
        const bool native = platform.value("family").toString() == "kylin"
            && platform.value("version_major").toString() == "11";
        const bool nativeReport = native && embedding.value("runtime").toString() == "kylin"
            && vector.value("runtime").toString() == "kylin";
        const double schema = version.value("schema_version").toDouble(-1);
        if (health.value("component").toString() != "pixiu-memory-backend"
            || version.value("component").toString() != "pixiu-memory-backend"
            || health.value("status").toString() != "ready" || health.value("database").toString() != "ok"
            || !text(version, "product_version") || !text(version, "api_version")
            || !version.value("agent_memory_api").isDouble()
            || !version.value("schema_version").isDouble() || schema < 1 || schema > 2147483647
            || schema != static_cast<int>(schema)
            || health.value("schema_version") != version.value("schema_version")
            || health.value("product_version") != version.value("product_version")
            || !text(platform, "family") || !text(platform, "version_major")
            || !platform.value("v11").isBool() || platform.value("v11").toBool() != native
            || !adapter(embedding) || !adapter(vector) || !caps.value("contest_ready").isBool()
            || caps.value("contest_ready").toBool() != nativeReport) {
            details->clear();
            status->setText(tr("响应缺失、未就绪或互相矛盾，不能确认服务状态。请重新读取。"));
            return;
        }
        const auto product = version.value("product_version").toString();
        const auto api = version.value("api_version").toString();
        const bool compatible = QRegularExpression(QStringLiteral("^0\\.5\\.[0-9]+$")).match(api).hasMatch()
            && version.value("agent_memory_api").toDouble() == 1;
        QStringList lines{
            tr("后端组件与数据库：就绪（本次读取）"),
            tr("桌面产品版本：%1").arg(QStringLiteral(PIXIU_VERSION)),
            tr("后端产品版本：%1").arg(product),
            tr("HTTP API：%1 · Agent Memory API：%2 · 数据库 schema：%3")
                .arg(api).arg(version.value("agent_memory_api").toDouble()).arg(schema),
            compatible ? tr("接口版本：属于当前已验证范围") : tr("接口版本：不在当前已验证范围，管理操作可能不兼容"),
            product == QStringLiteral(PIXIU_VERSION) ? tr("产品版本：一致") : tr("产品版本：不一致，请核对安装与后端地址"),
            tr("平台：%1 %2").arg(platform.value("family").toString(), platform.value("version_major").toString()),
            tr("Embedding：配置 %1 → 实际 %2").arg(embedding.value("configured").toString(), embedding.value("runtime").toString()),
            tr("向量存储：配置 %1 → 实际 %2").arg(vector.value("configured").toString(), vector.value("runtime").toString()),
            nativeReport ? tr("能力报告：麒麟 V11 与双原生 SDK；不代表完整验收通过")
                         : tr("能力报告：未同时满足麒麟 V11 与双原生 SDK；可移植能力不作为原生验收")};
        details->setPlainText(lines.join(QLatin1Char('\n')));
        status->setText(tr("读取完成：%1。以上为读取快照，服务变化后请刷新。")
            .arg(QDateTime::currentDateTime().toString(Qt::ISODate)));
    });
}
}
