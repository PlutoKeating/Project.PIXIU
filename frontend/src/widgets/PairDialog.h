#ifndef PIXIU_PAIR_DIALOG_H
#define PIXIU_PAIR_DIALOG_H

#include <QDialog>
#include <QJsonObject>

class QComboBox;
class QLabel;
class QLineEdit;
class QPushButton;
class QStackedWidget;

// 设备配对对话框：按 docs/API.md 契约收集配对方式与 PIN。
//
// PIN 模式：粘贴另一台设备生成的令牌 + 6 位 PIN 后发射 pairRequested。
// QR 模式：经 /sync/token 生成本机配对令牌，渲染二维码供其他设备扫码
//（无 libqrencode 时降级为可复制的令牌文本），不伪造配对结果。
class PairDialog : public QDialog
{
    Q_OBJECT

public:
    explicit PairDialog(QWidget *parent = nullptr);

    // 显示并前置（复用唤起流程）。
    void showAndFocus();

    // 配对请求结果反馈（应用层接线 transport 后调用）。
    void setResultFeedback(bool ok, const QString &message);

    // 展示 /sync/token 返回的本机配对令牌（含 QR 渲染/文本降级）。
    void setPairingToken(const QJsonObject &response);
    // 令牌生成失败反馈。
    void setPairingTokenError(const QString &message);

signals:
    // 契约载荷：{"method":"PIN"|"QR","pin":...,"token":...}。
    void pairRequested(const QJsonObject &payload);
    // 请求生成本机配对令牌（载荷 {"method":"QR","ttl_seconds":300}）。
    void tokenGenerationRequested(const QJsonObject &payload);
    // 取消 / Esc / 窗口关闭。
    void cancelled();

private slots:
    void updateMethodState();
    void updateConfirmEnabled();

private:
    void generateToken();
    void renderToken(const QString &token);

    QComboBox *m_methodCombo = nullptr;
    QStackedWidget *m_methodStack = nullptr;
    QLineEdit *m_tokenInput = nullptr;
    QLineEdit *m_pinInput = nullptr;
    QPushButton *m_confirmButton = nullptr;
    QLabel *m_statusLabel = nullptr;
    QPushButton *m_generateButton = nullptr;
    QLabel *m_qrImageLabel = nullptr;
    QLabel *m_tokenLabel = nullptr;
};

#endif // PIXIU_PAIR_DIALOG_H
