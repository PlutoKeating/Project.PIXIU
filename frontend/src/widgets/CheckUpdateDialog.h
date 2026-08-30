#ifndef PIXIU_CHECK_UPDATE_DIALOG_H
#define PIXIU_CHECK_UPDATE_DIALOG_H

#include <QDialog>

class QLabel;

// 检查更新对话框：展示当前版本与升级指引，不做在线检查。
//
// 参赛语境如实——不承诺不存在的 OTA 能力；真实在线拉取最新版本号
// 为设计 spec 明确标注的未来扩展（不引入网络请求与离线依赖）。
class CheckUpdateDialog : public QDialog
{
    Q_OBJECT

public:
    explicit CheckUpdateDialog(QWidget *parent = nullptr);

    void showAndFocus();

private:
    QLabel *m_bodyLabel = nullptr;
};

#endif // PIXIU_CHECK_UPDATE_DIALOG_H
