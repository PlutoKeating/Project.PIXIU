#include "ForgetPage.h"
#include "services/HttpBackendTransport.h"
#include <QComboBox>
#include <QJsonArray>
#include <QLabel>
#include <QLineEdit>
#include <QPlainTextEdit>
#include <QPushButton>
#include <QTimer>
#include <QVBoxLayout>

namespace pixiu {
ForgetPage::ForgetPage(QWidget *parent, BackendTransport *transport)
    : QWidget(parent), m_transport(transport ? transport : new HttpBackendTransport(this))
{
    auto *layout = new QVBoxLayout(this);
    auto *notice = new QLabel(tr("遗忘会隐藏知识并删除其向量；共享知识还会生成同步墓碑。原始证据、关系和全文索引载荷并非物理擦除，关联数量只是影响预览。请核对下面的实际目标；本界面不提供撤销。"), this);
    notice->setWordWrap(true);
    layout->addWidget(notice);
    m_scope = new QComboBox(this);
    m_scope->setObjectName(QStringLiteral("forgetScope"));
    m_scope->addItem(tr("本机个人记忆"), QStringLiteral("user:local"));
    m_scope->addItem(tr("家庭共享记忆"), QStringLiteral("shared:home"));
    layout->addWidget(m_scope);
    m_command = new QLineEdit(this);
    m_command->setObjectName(QStringLiteral("forgetCommand"));
    m_command->setMaxLength(4096);
    m_command->setPlaceholderText(tr("描述要遗忘的知识，例如：忘记四月份电费账单"));
    layout->addWidget(m_command);
    m_preview = new QPushButton(tr("预览匹配目标（不执行遗忘）"), this);
    m_preview->setObjectName(QStringLiteral("forgetPreview"));
    layout->addWidget(m_preview);
    m_targets = new QPlainTextEdit(this);
    m_targets->setObjectName(QStringLiteral("forgetTargets"));
    m_targets->setReadOnly(true);
    layout->addWidget(m_targets, 1);
    m_cancel = new QPushButton(tr("取消并清除本页预览"), this);
    m_cancel->setObjectName(QStringLiteral("forgetCancel"));
    layout->addWidget(m_cancel);
    m_confirm = new QPushButton(tr("已核对以上目标，确认遗忘"), this);
    m_confirm->setObjectName(QStringLiteral("forgetConfirm"));
    m_confirm->setAutoDefault(false);
    layout->addWidget(m_confirm);
    m_status = new QLabel(tr("先选择范围并预览。输入描述本身不会执行遗忘。"), this);
    m_status->setObjectName(QStringLiteral("forgetStatus"));
    m_status->setTextFormat(Qt::PlainText);
    m_status->setWordWrap(true);
    layout->addWidget(m_status);
    m_expiry = new QTimer(this);
    m_expiry->setObjectName(QStringLiteral("forgetExpiry"));
    m_expiry->setSingleShot(true);
    connect(m_expiry, &QTimer::timeout, this, [this]() {
        invalidate();
        m_status->setText(tr("预览凭证已到期，请重新预览后确认。"));
    });
    connect(m_command, &QLineEdit::textChanged, this, [this]() { invalidate(); });
    connect(m_scope, QOverload<int>::of(&QComboBox::currentIndexChanged), this, [this]() { invalidate(); });
    connect(m_cancel, &QPushButton::clicked, this, [this]() {
        if (m_pending != Pending::None) return;
        invalidate();
        m_status->setText(tr("已取消；未发送遗忘确认。"));
    });
    connect(m_preview, &QPushButton::clicked, this, [this]() {
        if (m_pending != Pending::None || m_command->text().trimmed().isEmpty()) return;
        invalidate();
        m_payload = {{"command", m_command->text().trimmed()}, {"scope", m_scope->currentData().toString()}, {"confirm", false}};
        m_pending = Pending::Preview;
        m_clock.start();
        controls();
        m_status->setText(tr("正在读取目标预览…"));
        m_transport->reviewedForget(m_payload);
    });
    connect(m_confirm, &QPushButton::clicked, this, [this]() {
        if (m_pending != Pending::None || m_token.isEmpty()) return;
        auto payload = m_payload;
        payload.insert("confirm", true);
        payload.insert("confirmation_token", m_token);
        m_token.clear();
        m_expiry->stop();
        m_pending = Pending::Confirm;
        controls();
        m_status->setText(tr("正在执行遗忘。请勿重复操作；失败时也可能已部分生效。"));
        m_transport->reviewedForget(payload);
    });
    connect(m_transport, &BackendTransport::forgetResult, this, [this](const QJsonObject &response) {
        if (m_pending == Pending::None) return;
        const bool preview = m_pending == Pending::Preview;
        m_pending = Pending::None;
        if (preview) {
            const auto targets = response.value("targets").toArray();
            const auto token = response.value("confirmation_token").toString();
            const int ttl = response.value("expires_in_seconds").toInt();
            const qint64 remaining = qint64(ttl) * 1000 - m_clock.elapsed();
            bool valid = response.value("targets").isArray() && !token.isEmpty() && ttl > 0 && ttl <= 120 && remaining > 0;
            QStringList lines;
            for (const auto &value : targets) {
                const auto target = value.toObject();
                valid = valid && !target.value("id").toString().isEmpty() && target.value("version").toInt() > 0
                    && target.value("scope").toString() == m_payload.value("scope").toString();
                lines << tr("%1\n%2 · 版本 %3 · %4").arg(target.value("title").toString(), target.value("id").toString())
                    .arg(target.value("version").toInt()).arg(target.value("scope").toString());
            }
            if (!valid) m_status->setText(tr("预览不完整、范围不匹配或已过期，禁止确认，请重试。"));
            else if (targets.isEmpty()) m_status->setText(tr("没有匹配目标，未执行遗忘。"));
            else {
                const auto cascade = response.value("cascade").toObject();
                lines << tr("关联预估：证据 %1 条，关系 %2 条（不表示物理删除）")
                    .arg(cascade.value("evidence_count").toInt()).arg(cascade.value("relation_count").toInt());
                m_targets->setPlainText(lines.join(QStringLiteral("\n\n")));
                for (const auto &target : targets) m_targetIds << target.toObject().value("id").toString();
                m_token = token;
                m_expiry->start(int(remaining));
                m_status->setText(tr("请逐项核对后确认；取消不会发送写请求。"));
                m_cancel->setFocus();
            }
        } else if (response.value("status").toString() == "forgotten" && response.value("forgotten_ids").isArray()) {
            QStringList ids;
            for (const auto &id : response.value("forgotten_ids").toArray()) ids << id.toString();
            ids.sort();
            m_targetIds.sort();
            if (ids != m_targetIds) {
                m_status->setText(tr("遗忘结果与预览目标不一致，请检索核对；禁止沿用此次确认。"));
                controls();
                return;
            }
            m_targets->clear();
            m_status->setText(tr("后端确认遗忘 %1 条知识。跨设备送达尚未验证。")
                .arg(response.value("forgotten_ids").toArray().size()));
            emit memoryForgotten();
        } else m_status->setText(tr("确认响应异常，结果未确认；请检索核对，不要重复确认。"));
        controls();
    });
    connect(m_transport, &BackendTransport::errorOccurred, this, [this](const QString &, const QString &message, const QString &) {
        if (m_pending == Pending::None) return;
        const bool confirming = m_pending == Pending::Confirm;
        m_pending = Pending::None;
        invalidate();
        m_status->setText(confirming ? tr("遗忘结果未确认：%1。可能部分生效，请先检索核对；再次操作必须重新预览。").arg(message)
            : tr("预览失败：%1。可重试。").arg(message));
    });
    controls();
}
void ForgetPage::invalidate()
{
    m_token.clear();
    m_targetIds.clear();
    m_targets->clear();
    m_expiry->stop();
    controls();
}
void ForgetPage::controls()
{
    const bool idle = m_pending == Pending::None;
    m_command->setEnabled(idle);
    m_scope->setEnabled(idle);
    m_preview->setEnabled(idle && !m_command->text().trimmed().isEmpty());
    m_confirm->setEnabled(idle && !m_token.isEmpty());
    m_cancel->setEnabled(idle);
}
}
