#ifndef PIXIU_INPUT_BAR_H
#define PIXIU_INPUT_BAR_H

#include <QList>
#include <QWidget>

#include "services/BackendTypes.h"

class QLabel;
class QMenu;
class QPlainTextEdit;
class QPushButton;

// 输入栏（侧边助手底部第二视觉焦点）：
//   - 输入区上方的轻量 chip 快捷行（记忆/设置/录入/同步/更多），空间不足时
//     自动收缩进“更多”菜单，不挤爆窗口；
//   - 圆角输入卡片：多行输入（Enter 发送、Shift+Enter 换行）、左下角后端
//     状态 badge、右下角主题高亮发送按钮。
//
// 业务语义保持：回车/点击发送并清空；空文本不发送；附件入口不变。
class InputBar : public QWidget
{
    Q_OBJECT

public:
    explicit InputBar(QWidget *parent = nullptr);

    // 聚焦输入框（聊天框唤起时调用）。
    void focusInput();

    // 清空输入内容。
    void clearInput();

    // 恢复/预填输入内容（失败重试、建议卡片场景）。
    void setInputText(const QString &text);

    // 后端连接状态 -> 左下角 badge 与输入可用性。
    void setBackendState(ConnectionState state);

signals:
    void sendRequested(const QString &text);
    void attachRequested();
    // chip 快捷入口。
    void memoryPanelRequested();
    void settingsRequested();
    void syncPanelRequested();

protected:
    bool eventFilter(QObject *watched, QEvent *event) override;
    void resizeEvent(QResizeEvent *event) override;

private:
    void onSendClicked();
    void updateSendEnabled();
    void rebuildChipIcons();
    void updateChipVisibility();
    void showMoreMenu();

    QPlainTextEdit *m_editor = nullptr;
    QPushButton *m_attachButton = nullptr;
    QPushButton *m_sendButton = nullptr;
    QLabel *m_stateBadge = nullptr;

    QPushButton *m_memoryChip = nullptr;
    QPushButton *m_settingsChip = nullptr;
    QPushButton *m_importChip = nullptr;
    QPushButton *m_syncChip = nullptr;
    QPushButton *m_moreChip = nullptr;
    QMenu *m_moreMenu = nullptr;
    QList<QPushButton *> m_chips;

    ConnectionState m_state = ConnectionState::Disconnected;
};

#endif // PIXIU_INPUT_BAR_H
