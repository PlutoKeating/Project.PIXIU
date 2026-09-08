#ifndef PIXIU_INFO_DIALOG_H
#define PIXIU_INFO_DIALOG_H

#include <QDialog>
#include <QString>

class QTextBrowser;

// 通用只读文档对话框：标题 + 只读正文 + 关闭按钮。
//
// 关于 PIXIU / 数据与联网 / 第三方组件说明复用；正文由调用方以纯文本传入
// （多段以空行分隔），渲染为只读可滚动文本。对话框非模态：关闭只关
// 闭本弹窗；正式设置页拥有实例，宿主退出保护检查可见对话框。
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
