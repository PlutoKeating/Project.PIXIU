#include "widgets/PairDialog.h"

#include <QComboBox>
#include <QHBoxLayout>
#include <QIntValidator>
#include <QLabel>
#include <QLineEdit>
#include <QPushButton>
#include <QStackedWidget>
#include <QVBoxLayout>

namespace {
constexpr int kPinLength = 6;
}

PairDialog::PairDialog(QWidget *parent)
    : QDialog(parent)
{
    setWindowTitle(tr("配对新设备"));
    setModal(false);

    QLabel *scopeLabel = new QLabel(tr("加入共享域 shared:home"), this);
    scopeLabel->setObjectName(QStringLiteral("pairScopeLabel"));

    m_methodCombo = new QComboBox(this);
    m_methodCombo->addItem(tr("PIN 输入"));
    m_methodCombo->addItem(tr("二维码扫码"));
    m_methodCombo->setObjectName(QStringLiteral("pairMethodCombo"));
    m_methodCombo->setAccessibleName(tr("配对方式"));

    // PIN 输入页。
    QWidget *pinPage = new QWidget(this);
    QVBoxLayout *pinLayout = new QVBoxLayout(pinPage);
    pinLayout->setContentsMargins(0, 0, 0, 0);

    m_pinInput = new QLineEdit(pinPage);
    m_pinInput->setObjectName(QStringLiteral("pairPinInput"));
    m_pinInput->setAccessibleName(tr("PIN 输入框"));
    m_pinInput->setMaxLength(kPinLength);
    m_pinInput->setValidator(new QIntValidator(0, 999999, m_pinInput));
    m_pinInput->setPlaceholderText(tr("输入 6 位 PIN"));
    m_pinInput->setEchoMode(QLineEdit::Password);
    pinLayout->addWidget(m_pinInput);

    // 二维码页（令牌契约待后端落地，占位提示）。
    QWidget *qrPage = new QWidget(this);
    QVBoxLayout *qrLayout = new QVBoxLayout(qrPage);
    qrLayout->setContentsMargins(0, 0, 0, 0);
    QLabel *qrLabel = new QLabel(tr("二维码令牌待后端契约（foundation/sync）"), qrPage);
    qrLabel->setObjectName(QStringLiteral("pairQrPlaceholder"));
    qrLabel->setWordWrap(true);
    qrLayout->addWidget(qrLabel);

    m_methodStack = new QStackedWidget(this);
    m_methodStack->addWidget(pinPage);
    m_methodStack->addWidget(qrPage);

    m_statusLabel = new QLabel(this);
    m_statusLabel->setObjectName(QStringLiteral("pairStatusLabel"));
    m_statusLabel->setWordWrap(true);
    m_statusLabel->hide();

    QPushButton *cancelButton = new QPushButton(tr("取消"), this);
    cancelButton->setObjectName(QStringLiteral("pairCancelButton"));
    cancelButton->setAccessibleName(tr("取消配对"));
    m_confirmButton = new QPushButton(tr("完成配对"), this);
    m_confirmButton->setObjectName(QStringLiteral("pairConfirmButton"));
    m_confirmButton->setAccessibleName(tr("完成配对"));
    m_confirmButton->setDefault(true);

    connect(cancelButton, &QPushButton::clicked, this, [this]() {
        emit cancelled();
        hide();
    });
    connect(m_confirmButton, &QPushButton::clicked, this, [this]() {
        QJsonObject payload;
        payload.insert(QStringLiteral("method"), QStringLiteral("PIN"));
        payload.insert(QStringLiteral("pin"), m_pinInput->text().trimmed());
        payload.insert(QStringLiteral("token"), QString());
        emit pairRequested(payload);
        hide();
    });
    // 键盘可达：Esc / 窗口关闭视为取消，不发射配对请求。
    connect(this, &QDialog::rejected, this, [this]() {
        emit cancelled();
    });
    connect(m_methodCombo, QOverload<int>::of(&QComboBox::currentIndexChanged),
            this, &PairDialog::updateMethodState);
    connect(m_pinInput, &QLineEdit::textChanged,
            this, &PairDialog::updateConfirmEnabled);

    QHBoxLayout *methodRow = new QHBoxLayout();
    methodRow->addWidget(m_methodCombo);
    methodRow->addStretch(1);

    QHBoxLayout *buttonRow = new QHBoxLayout();
    buttonRow->addStretch(1);
    buttonRow->addWidget(cancelButton);
    buttonRow->addWidget(m_confirmButton);

    QVBoxLayout *layout = new QVBoxLayout(this);
    layout->addWidget(scopeLabel);
    layout->addLayout(methodRow);
    layout->addWidget(m_methodStack);
    layout->addWidget(m_statusLabel);
    layout->addLayout(buttonRow);

    updateMethodState();
}

void PairDialog::showAndFocus()
{
    show();
    raise();
    activateWindow();
    if (m_methodCombo->currentIndex() == 0 && m_pinInput) {
        m_pinInput->setFocus();
    }
}

void PairDialog::setResultFeedback(bool ok, const QString &message)
{
    m_statusLabel->setText(message);
    m_statusLabel->setStyleSheet(
        ok ? QStringLiteral("color: #1a7f37;")
           : QStringLiteral("color: #d93025;"));
    m_statusLabel->show();
}

void PairDialog::updateMethodState()
{
    const bool pinMode = m_methodCombo->currentIndex() == 0;
    m_methodStack->setCurrentIndex(pinMode ? 0 : 1);
    updateConfirmEnabled();
}

void PairDialog::updateConfirmEnabled()
{
    const bool pinMode = m_methodCombo->currentIndex() == 0;
    // 二维码令牌契约未落地前禁用确认；PIN 模式要求恰好 6 位数字。
    m_confirmButton->setEnabled(
        pinMode && m_pinInput->text().trimmed().length() == kPinLength);
}
