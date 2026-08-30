#ifndef PIXIU_INFO_DIALOG_H
#define PIXIU_INFO_DIALOG_H

#include <QDialog>
#include <QString>

class QTextBrowser;

// 通用只读文档对话框：标题 + 只读正文 + 关闭按钮。
//
// 关于 PIXIU / 服务条款 / 隐私政策三页复用；正文由调用方以纯文本传入
// （多段以空行分隔），渲染为只读可滚动文本。对话框非模态：关闭只关
// 闭本弹窗，不影响聊天窗交互（与设置/遗忘等弹窗一致）。
class InfoDialog : public QDialog
{
    Q_OBJECT

public:
    explicit InfoDialog(const QString &title, const QString &body,
                        QWidget *parent = nullptr);

    void showAndFocus();

private:
    QTextBrowser *m_textBrowser = nullptr;
};

#endif // PIXIU_INFO_DIALOG_H
