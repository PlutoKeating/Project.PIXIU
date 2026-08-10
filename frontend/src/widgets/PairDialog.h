#ifndef PIXIU_PAIR_DIALOG_H
#define PIXIU_PAIR_DIALOG_H

#include <QDialog>
#include <QJsonObject>

class QComboBox;
class QLabel;
class QLineEdit;
class QPushButton;
class QStackedWidget;

// 设备配对对话框：按 docs/API.md §3.8 契约收集配对方式与 PIN。
//
// Phase 6 后端 /sync/pair 落地前，二维码令牌区为占位；确认后发射
// pairRequested，由应用层发送请求并如实呈现 not_implemented / 网络错误，
// 不在生产路径内置假成功。
class PairDialog : public QDialog
{
    Q_OBJECT

public:
    explicit PairDialog(QWidget *parent = nullptr);

    // 显示并前置（复用唤起流程）。
    void showAndFocus();

    // 配对请求结果反馈（应用层接线 transport 后调用）。
    void setResultFeedback(bool ok, const QString &message);

signals:
    // 契约载荷：{"method":"PIN"|"QR","pin":...,"token":...}。
    void pairRequested(const QJsonObject &payload);
    // 取消 / Esc / 窗口关闭。
    void cancelled();

private slots:
    void updateMethodState();
    void updateConfirmEnabled();

private:
    QComboBox *m_methodCombo = nullptr;
    QStackedWidget *m_methodStack = nullptr;
    QLineEdit *m_tokenInput = nullptr;
    QLineEdit *m_pinInput = nullptr;
    QPushButton *m_confirmButton = nullptr;
    QLabel *m_statusLabel = nullptr;
};

#endif // PIXIU_PAIR_DIALOG_H
