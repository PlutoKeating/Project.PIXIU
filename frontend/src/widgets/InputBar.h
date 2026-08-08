#ifndef PIXIU_INPUT_BAR_H
#define PIXIU_INPUT_BAR_H

#include <QWidget>

class QLineEdit;
class QPushButton;

// 输入栏：附件按钮 + 文本输入 + 发送按钮。
//
// 回车或点击发送时发射 sendRequested 并清空输入；空文本不发送。
class InputBar : public QWidget
{
    Q_OBJECT

public:
    explicit InputBar(QWidget *parent = nullptr);

    // 聚焦输入框（聊天框唤起时调用）。
    void focusInput();

    // 清空输入内容。
    void clearInput();

    // 恢复/预填输入内容（失败重试场景）。
    void setInputText(const QString &text);

signals:
    void sendRequested(const QString &text);
    void attachRequested();

private:
    void onSendClicked();
    void onReturnPressed();

    QLineEdit *m_lineEdit = nullptr;
    QPushButton *m_sendButton = nullptr;
};

#endif // PIXIU_INPUT_BAR_H
