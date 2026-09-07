#include "PairingDialog.h"
#include "services/HttpBackendTransport.h"
#include <QComboBox>
#include <QLabel>
#include <QLineEdit>
#include <QPlainTextEdit>
#include <QPushButton>
#include <QRegularExpression>
#include <QRegularExpressionValidator>
#include <QTimer>
#include <QVBoxLayout>

namespace pixiu {
namespace {
bool validPin(const QString &pin)
{
    return QRegularExpression(QStringLiteral("^[0-9]{6}$")).match(pin).hasMatch();
}
}
PairingDialog::PairingDialog(QWidget *parent, BackendTransport *transport)
    : QDialog(parent), m_transport(transport ? transport : new HttpBackendTransport(this))
{
    setWindowTitle(tr("交换配对令牌"));
    resize(580, 650);
    auto *layout = new QVBoxLayout(this);
    auto *hint = new QLabel(tr("在两台设备上分别生成令牌，通过可信渠道交换，并分别提交对方令牌以建立双向信任。双方必须属于相同共享域。PIN 请通过另一可信渠道告知对方；不要公开令牌或放入截图。"), this);
    hint->setWordWrap(true);
    layout->addWidget(hint);
    m_method = new QComboBox(this);
    m_method->setObjectName(QStringLiteral("pairingMethod"));
    m_method->addItem(tr("PIN 保护令牌"), QStringLiteral("PIN"));
    m_method->addItem(tr("QR 格式令牌（文本交换）"), QStringLiteral("QR"));
    layout->addWidget(m_method);
    m_localPin = new QLineEdit(this);
    m_localPin->setObjectName(QStringLiteral("pairingLocalPin"));
    m_localPin->setPlaceholderText(tr("为本机令牌设置 6 位数字 PIN"));
    m_localPin->setAccessibleName(tr("本机令牌 PIN"));
    m_remotePin = new QLineEdit(this);
    m_remotePin->setObjectName(QStringLiteral("pairingRemotePin"));
    m_remotePin->setPlaceholderText(tr("对方告知的 6 位数字 PIN"));
    m_remotePin->setAccessibleName(tr("对端令牌 PIN"));
    for (auto *pin : {m_localPin, m_remotePin}) {
        pin->setMaxLength(6);
        pin->setEchoMode(QLineEdit::Password);
        pin->setValidator(new QRegularExpressionValidator(QRegularExpression(QStringLiteral("[0-9]{0,6}")), pin));
        connect(pin, &QLineEdit::textChanged, this, [this]() { controls(); });
    }
    layout->addWidget(m_localPin);
    m_generate = new QPushButton(tr("生成本机令牌（有效期 5 分钟）"), this);
    m_generate->setObjectName(QStringLiteral("pairingGenerate"));
    layout->addWidget(m_generate);
    m_localToken = new QPlainTextEdit(this);
    m_localToken->setObjectName(QStringLiteral("pairingLocalToken"));
    m_localToken->setAccessibleName(tr("本机配对令牌，仅交给可信设备"));
    m_localToken->setReadOnly(true);
    layout->addWidget(m_localToken, 1);
    m_tokenStatus = new QLabel(tr("尚未生成令牌。"), this);
    m_tokenStatus->setWordWrap(true);
    layout->addWidget(m_tokenStatus);
    layout->addWidget(new QLabel(tr("粘贴另一台设备的令牌（方式必须与上方选择一致）"), this));
    m_remoteToken = new QPlainTextEdit(this);
    m_remoteToken->setObjectName(QStringLiteral("pairingRemoteToken"));
    m_remoteToken->setAccessibleName(tr("对端配对令牌"));
    layout->addWidget(m_remoteToken, 1);
    layout->addWidget(m_remotePin);
    m_pair = new QPushButton(tr("验证对端令牌并建立本地信任"), this);
    m_pair->setObjectName(QStringLiteral("pairingSubmit"));
    layout->addWidget(m_pair);
    m_status = new QLabel(tr("此操作只更新本机信任；不证明对端已信任本机或数据已同步。"), this);
    m_status->setObjectName(QStringLiteral("pairingStatus"));
    m_status->setWordWrap(true);
    m_status->setTextFormat(Qt::PlainText);
    layout->addWidget(m_status);
    m_close = new QPushButton(tr("关闭并清除本页令牌"), this);
    layout->addWidget(m_close);
    m_expiry = new QTimer(this);
    m_expiry->setObjectName(QStringLiteral("pairingExpiry"));
    m_expiry->setSingleShot(true);
    connect(m_expiry, &QTimer::timeout, this, [this]() {
        m_localToken->clear();
        m_tokenStatus->setText(tr("本机令牌已到期并从界面清除，请重新生成。"));
    });
    connect(m_remoteToken, &QPlainTextEdit::textChanged, this, [this]() { controls(); });
    connect(m_method, QOverload<int>::of(&QComboBox::currentIndexChanged), this, [this]() {
        m_expiry->stop();
        m_localToken->clear();
        m_tokenStatus->setText(tr("方式已切换，请按当前方式重新生成令牌。旧令牌在后端到期前仍可能有效。"));
        controls();
    });
    connect(m_close, &QPushButton::clicked, this, &PairingDialog::reject);
    connect(m_generate, &QPushButton::clicked, this, [this]() {
        if (!m_generate->isEnabled()) return;
        m_requestedMethod = m_method->currentData().toString();
        QJsonObject payload{{"method", m_requestedMethod}, {"ttl_seconds", 300}};
        if (m_requestedMethod == "PIN") payload.insert("pin", m_localPin->text());
        m_expiry->stop();
        m_localToken->clear();
        m_pending = Pending::Token;
        controls();
        m_tokenStatus->setText(tr("正在生成令牌…"));
        m_generationClock.start();
        m_transport->createPairingToken(payload);
    });
    connect(m_pair, &QPushButton::clicked, this, [this]() {
        if (!m_pair->isEnabled()) return;
        QJsonObject payload{{"method", m_method->currentData().toString()}, {"token", m_remoteToken->toPlainText().trimmed()}};
        if (m_method->currentData() == "PIN") payload.insert("pin", m_remotePin->text());
        m_pending = Pending::Pair;
        controls();
        m_status->setText(tr("后端正在验证令牌、有效期及信任信息…"));
        m_transport->pairDevice(payload);
    });
    connect(m_transport, &BackendTransport::pairingTokenResult, this, [this](const QJsonObject &response) {
        if (m_pending != Pending::Token) return;
        m_pending = Pending::None;
        const auto token = response.value("token").toString();
        const int ttl = response.value("ttl_seconds").toInt();
        const qint64 remaining = qint64(ttl) * 1000 - m_generationClock.elapsed();
        if (token.isEmpty() || token.size() > 16384 || response.value("method").toString() != m_requestedMethod
            || ttl < 1 || ttl > 300 || remaining <= 0) {
            m_tokenStatus->setText(tr("令牌响应无效或已过期，请重新生成。"));
        } else {
            m_localToken->setPlainText(token);
            m_expiry->start(int(remaining));
            m_tokenStatus->setText(tr("令牌已生成；到期自动清除。生成令牌不会自动建立任何设备信任。"));
        }
        controls();
    });
    connect(m_transport, &BackendTransport::pairResult, this, [this](const QJsonObject &response) {
        if (m_pending != Pending::Pair) return;
        m_pending = Pending::None;
        if (response.value("status").toString() != "paired" || response.value("peer_id").toString().isEmpty()
            || response.value("domain").toString().isEmpty()) {
            m_status->setText(tr("响应不完整，未确认建立信任；请关闭后刷新节点核对，勿盲目重复提交。"));
        } else {
            m_remoteToken->clear();
            m_remotePin->clear();
            m_status->setText(tr("本机已信任设备 %1（%2）。请在对端完成反向令牌交换；实际传输尚未验证。")
                .arg(response.value("peer_id").toString(), response.value("domain").toString()));
            emit localTrustEstablished();
        }
        controls();
    });
    connect(m_transport, &BackendTransport::errorOccurred, this, [this](const QString &, const QString &message, const QString &) {
        if (m_pending == Pending::None) return;
        if (m_pending == Pending::Token) m_tokenStatus->setText(tr("令牌生成失败：%1").arg(message));
        else m_status->setText(tr("验证未确认成功：%1。输入已保留；令牌可能已到期、已使用或不匹配。网络错误时请先刷新节点核对。").arg(message));
        m_pending = Pending::None;
        controls();
    });
    controls();
}
void PairingDialog::controls()
{
    const bool idle = m_pending == Pending::None;
    const bool pin = m_method->currentData() == "PIN";
    m_method->setEnabled(idle);
    m_localPin->setEnabled(idle && pin);
    m_remotePin->setEnabled(idle && pin);
    m_remoteToken->setEnabled(idle);
    m_generate->setEnabled(idle && (!pin || validPin(m_localPin->text())));
    const auto token = m_remoteToken->toPlainText().trimmed();
    m_pair->setEnabled(idle && !token.isEmpty() && token.size() <= 16384 && (!pin || validPin(m_remotePin->text())));
    m_close->setEnabled(idle);
}
void PairingDialog::reject()
{
    if (m_pending != Pending::None) return;
    m_expiry->stop();
    m_localToken->clear();
    m_remoteToken->clear();
    m_localPin->clear();
    m_remotePin->clear();
    m_tokenStatus->setText(tr("界面令牌已清除；未到期令牌不会因此在后端撤销。"));
    QDialog::reject();
}
}
