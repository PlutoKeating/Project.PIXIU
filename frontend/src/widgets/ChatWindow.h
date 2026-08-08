#ifndef PIXIU_CHAT_WINDOW_H
#define PIXIU_CHAT_WINDOW_H

#include <QWidget>

#include "services/BackendTypes.h"

class QLabel;
class QPushButton;
class QPropertyAnimation;
class InputBar;
class MessageList;

// 聊天主窗口：无边框圆角浮层，顶栏（标题 + 状态 + 面板/关闭）。
//
// 本阶段提供窗口壳与显示/隐藏/焦点行为；消息列表与输入栏由后续 feature 填充。
class ChatWindow : public QWidget
{
    Q_OBJECT

public:
    explicit ChatWindow(QWidget *parent = nullptr);

    // 淡入并获取焦点（窗口被反复唤起时保持此语义）。
    void showAndFocus();
    // 淡出隐藏。
    void hideAnimated();

    // 当前是否可见。
    bool isChatVisible() const;

    // 消息列表（供应用层追加消息/设置加载态）。
    MessageList *messageList() const;

    // 后端连接状态 -> 顶栏状态与输入可用性。
    void setBackendState(ConnectionState state);

    // 恢复用户输入（查询失败重试）。
    void restoreInput(const QString &text);

signals:
    void closeRequested();
    void openPanelRequested();
    void sendRequested(const QString &text);
    void attachRequested();
    // 窗口从隐藏变为可见时发射（用于角标清除等状态复位）。
    void shown();

protected:
    void keyPressEvent(QKeyEvent *event) override;
    void paintEvent(QPaintEvent *event) override;
    void moveEvent(QMoveEvent *event) override;
    void closeEvent(QCloseEvent *event) override;

private:
    void animateOpacity(qreal target);

    QLabel *m_statusLabel = nullptr;
    InputBar *m_inputBar = nullptr;
    MessageList *m_messageList = nullptr;
    QPropertyAnimation *m_opacityAnimation = nullptr;
    QPoint m_rememberedPos;

    static constexpr int kWindowWidth = 420;
    static constexpr int kWindowHeight = 560;
    static constexpr int kAnimationMs = 150;
};

#endif // PIXIU_CHAT_WINDOW_H
