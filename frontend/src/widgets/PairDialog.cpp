#include "widgets/PairDialog.h"

#include "app/UiTokens.h"

#include <QComboBox>
#include <QHBoxLayout>
#include <QImage>
#include <QIntValidator>
#include <QLabel>
#include <QLineEdit>
#include <QPixmap>
#include <QPushButton>
#include <QStackedWidget>
#include <QVBoxLayout>

#ifdef PIXIU_HAVE_QRENCODE
#include <qrencode.h>
#endif

namespace {
constexpr int kPinLength = 6;
}

PairDialog::PairDialog(QWidget *parent)
    : QDialog(parent)
{
    setWindowTitle(tr("配对新设备"));
    setModal(false);
    // 默认内容尺寸下对话框过窄（PIN 输入 / 按钮局促）；固定舒适最小宽度，
    // 明暗主题与英文文案下保持一致观感（ARCHITECTURE §7.3）。
    setMinimumWidth(280);

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

    m_tokenInput = new QLineEdit(pinPage);
    m_tokenInput->setObjectName(QStringLiteral("pairTokenInput"));
    m_tokenInput->setAccessibleName(tr("配对令牌输入框"));
    m_tokenInput->setPlaceholderText(
        tr("另一台设备生成的配对令牌（必填）"));
    pinLayout->addWidget(m_tokenInput);

    m_pinInput = new QLineEdit(pinPage);
    m_pinInput->setObjectName(QStringLiteral("pairPinInput"));
    m_pinInput->setAccessibleName(tr("PIN 输入框"));
    m_pinInput->setMaxLength(kPinLength);
    m_pinInput->setValidator(new QIntValidator(0, 999999, m_pinInput));
    m_pinInput->setPlaceholderText(tr("输入 6 位 PIN"));
    m_pinInput->setEchoMode(QLineEdit::Password);
    pinLayout->addWidget(m_pinInput);

    connect(m_tokenInput, &QLineEdit::textChanged,
            this, &PairDialog::updateConfirmEnabled);

    // 二维码页：生成本机配对令牌并渲染二维码（无 libqrencode 时降级为文本）。
    QWidget *qrPage = new QWidget(this);
    QVBoxLayout *qrLayout = new QVBoxLayout(qrPage);
    qrLayout->setContentsMargins(0, 0, 0, 0);
    qrLayout->setSpacing(ui::Spacing::XS);

    QLabel *qrHint = new QLabel(
        tr("其他设备扫码或复制令牌后，在本机粘贴完成配对。"), qrPage);
    qrHint->setWordWrap(true);

    m_generateButton = new QPushButton(tr("生成本机配对令牌"), qrPage);
    m_generateButton->setObjectName(QStringLiteral("pairGenerateTokenButton"));
    m_generateButton->setAccessibleName(tr("生成本机配对令牌"));
    m_generateButton->setCursor(Qt::PointingHandCursor);
    connect(m_generateButton, &QPushButton::clicked,
            this, &PairDialog::generateToken);

    m_qrImageLabel = new QLabel(qrPage);
    m_qrImageLabel->setObjectName(QStringLiteral("pairQrImage"));
    m_qrImageLabel->setAlignment(Qt::AlignCenter);
    m_qrImageLabel->setVisible(false);

    m_tokenLabel = new QLabel(qrPage);
    m_tokenLabel->setObjectName(QStringLiteral("pairTokenText"));
    m_tokenLabel->setTextInteractionFlags(Qt::TextSelectableByMouse);
    m_tokenLabel->setWordWrap(true);
    m_tokenLabel->setVisible(false);

    qrLayout->addWidget(qrHint);
    qrLayout->addWidget(m_generateButton, 0, Qt::AlignLeft);
    qrLayout->addWidget(m_qrImageLabel);
    qrLayout->addWidget(m_tokenLabel);
    qrLayout->addStretch(1);

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
    cancelButton->setCursor(Qt::PointingHandCursor);
    m_confirmButton = new QPushButton(tr("完成配对"), this);
    m_confirmButton->setObjectName(QStringLiteral("pairConfirmButton"));
    m_confirmButton->setAccessibleName(tr("完成配对"));
    m_confirmButton->setDefault(true);
    m_confirmButton->setCursor(Qt::PointingHandCursor);

    connect(cancelButton, &QPushButton::clicked, this, [this]() {
        emit cancelled();
        hide();
    });
    connect(m_confirmButton, &QPushButton::clicked, this, [this]() {
        QJsonObject payload;
        payload.insert(QStringLiteral("method"), QStringLiteral("PIN"));
        payload.insert(QStringLiteral("pin"), m_pinInput->text().trimmed());
        payload.insert(QStringLiteral("token"),
                       m_tokenInput->text().trimmed());
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
        ui::textStyle(ok ? ui::Role::Success : ui::Role::Error));
    m_statusLabel->show();
}

void PairDialog::generateToken()
{
    m_generateButton->setEnabled(false);
    m_tokenLabel->setText(tr("正在生成本机配对令牌…"));
    m_tokenLabel->setVisible(true);
    QJsonObject payload;
    payload.insert(QStringLiteral("method"), QStringLiteral("QR"));
    payload.insert(QStringLiteral("ttl_seconds"), 300);
    emit tokenGenerationRequested(payload);
}

void PairDialog::setPairingToken(const QJsonObject &response)
{
    m_generateButton->setEnabled(true);
    const QString token = response.value(QStringLiteral("token")).toString();
    if (token.isEmpty()) {
        setPairingTokenError(tr("后端未返回配对令牌"));
        return;
    }
    renderToken(token);
}

void PairDialog::setPairingTokenError(const QString &message)
{
    m_generateButton->setEnabled(true);
    m_qrImageLabel->setVisible(false);
    m_tokenLabel->setText(tr("令牌生成失败：%1").arg(message));
    m_tokenLabel->setStyleSheet(ui::textStyle(ui::Role::Error));
    m_tokenLabel->setVisible(true);
}

void PairDialog::renderToken(const QString &token)
{
#ifdef PIXIU_HAVE_QRENCODE
    QRcode *code = QRcode_encodeString(token.toUtf8().constData(),
                                       /*version=*/0, QR_ECLEVEL_M, QR_MODE_8,
                                       /*caseSensitive=*/1);
    if (code != nullptr) {
        const int scale = 4;
        const int quiet = 4;
        const int size = (code->width + quiet * 2) * scale;
        QImage image(size, size, QImage::Format_RGB32);
        image.fill(0xffffffff);
        for (int y = 0; y < code->width; ++y) {
            for (int x = 0; x < code->width; ++x) {
                if (code->data[y * code->width + x] & 1) {
                    for (int dy = 0; dy < scale; ++dy) {
                        for (int dx = 0; dx < scale; ++dx) {
                            image.setPixel(
                                (x + quiet) * scale + dx,
                                (y + quiet) * scale + dy, 0xff000000u);
                        }
                    }
                }
            }
        }
        QRcode_free(code);
        m_qrImageLabel->setPixmap(QPixmap::fromImage(image));
        m_qrImageLabel->setVisible(true);
        m_tokenLabel->setText(tr("扫码或复制令牌完成配对（5 分钟内有效）"));
        m_tokenLabel->setStyleSheet(QString());
        m_tokenLabel->setTextInteractionFlags(Qt::TextSelectableByMouse);
        m_tokenLabel->setVisible(true);
        return;
    }
#endif
    // 无 libqrencode 或编码失败：降级为可选中的令牌文本。
    m_qrImageLabel->setVisible(false);
    m_tokenLabel->setText(token);
    m_tokenLabel->setStyleSheet(QString());
    m_tokenLabel->setTextInteractionFlags(Qt::TextSelectableByMouse);
    m_tokenLabel->setVisible(true);
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
    // 二维码令牌契约未落地前禁用确认；PIN 模式要求令牌非空且 PIN 恰好 6 位数字
    //（后端 /sync/pair 校验 token 必填、pin 6 位 ASCII 数字）。
    m_confirmButton->setEnabled(
        pinMode
        && !m_tokenInput->text().trimmed().isEmpty()
        && m_pinInput->text().trimmed().length() == kPinLength);
}
