#ifndef PIXIU_FORGET_DIALOG_H
#define PIXIU_FORGET_DIALOG_H

#include <QDialog>
#include <QJsonArray>
#include <QJsonObject>

class QLabel;
class QPushButton;

// 遗忘二次确认对话框：展示影响范围（目标 + 级联清理），确认后才执行。
class ForgetDialog : public QDialog
{
    Q_OBJECT

public:
    explicit ForgetDialog(QWidget *parent = nullptr);

    // 设置待确认内容（来自 /forget confirm=false 响应）。
    void setForgetTargets(const QJsonArray &targets, const QJsonObject &cascade);

signals:
    void confirmed();
    void cancelled();

protected:
    // 危险操作默认聚焦“取消”：对话框显示时把键盘焦点放到取消按钮。
    void showEvent(QShowEvent *event) override;

private:
    QLabel *m_summaryLabel = nullptr;
};

#endif // PIXIU_FORGET_DIALOG_H
