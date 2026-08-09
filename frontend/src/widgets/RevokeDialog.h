#ifndef PIXIU_REVOKE_DIALOG_H
#define PIXIU_REVOKE_DIALOG_H

#include <QDialog>

class QLabel;

// 设备解绑二次确认对话框：展示设备名与不可逆影响，确认后才执行。
//
// 危险操作语义与 ForgetDialog 一致：默认聚焦“取消”，Esc/窗口关闭视为取消，
// 避免误触确认。
class RevokeDialog : public QDialog
{
    Q_OBJECT

public:
    explicit RevokeDialog(QWidget *parent = nullptr);

    // 设置待解绑设备名并显示前置。
    void setPeerName(const QString &name);
    void showAndFocus();

signals:
    void confirmed();
    void cancelled();

private:
    QLabel *m_nameLabel = nullptr;
};

#endif // PIXIU_REVOKE_DIALOG_H
