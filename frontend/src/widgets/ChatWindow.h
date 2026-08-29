#ifndef PIXIU_CHAT_WINDOW_H
#define PIXIU_CHAT_WINDOW_H

#include <QList>
#include <QWidget>

#include "services/BackendTypes.h"

class QLabel;
class QMenu;
class QPushButton;
class QPropertyAnimation;
class QStackedWidget;
class QVBoxLayout;
class InputBar;
class MessageList;

// 聊天主窗口：窄而高的侧边助手浮窗（无边框圆角浮层）。顶栏保持轻量——
// 左侧 Logo + 应用入口，右侧置顶/菜单/关闭三个主题感知图标按钮；消息区为
// 欢迎页（Logo + 问候 + 建议问题卡片）与消息流的自动切换；输入区为多行
// 卡片 + chip 快捷行 + 状态 badge（见 InputBar）。
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

    // 监控总闸状态 -> 输入区“⏸ 已暂停”徽标（InputBar 内部处理）。
    void setMonitorActive(bool active);

    // 恢复用户输入（查询失败重试）。
    void restoreInput(const QString &text);

    // 递送层动态洞察（B4-3）：渲染动态建议卡（title + summary），追加在
    // 静态建议卡之后；空数组是合法空态，保留静态兜底不渲染。
    void setInsights(const QJsonArray &insights);

signals:
    void closeRequested();
    void openPanelRequested();
    // 顶栏“设置”入口。
    void settingsRequested();
    // 同步面板入口（chip / 菜单）。
    void syncPanelRequested();
    // 用户拖动窗口后发射（供应用层持久化位置）。
    void moved(const QPoint &topLeft);
    void sendRequested(const QString &text);
    void attachRequested();
    // 窗口从隐藏变为可见时发射（用于角标清除等状态复位）。
    void shown();
    // 欢迎页“今日简报”建议卡点击（B4-3）：应用层据此拉取 /delivery/digest。
    void digestRequested();

protected:
    void keyPressEvent(QKeyEvent *event) override;
    void mousePressEvent(QMouseEvent *event) override;
    void mouseMoveEvent(QMouseEvent *event) override;
    void mouseReleaseEvent(QMouseEvent *event) override;
    void leaveEvent(QEvent *event) override;
    void paintEvent(QPaintEvent *event) override;
    void moveEvent(QMoveEvent *event) override;
    void closeEvent(QCloseEvent *event) override;

private:
    QWidget *buildWelcomeView();
    void animateOpacity(qreal target);
    enum class ResizeEdge {
        None, Left, Right, Top, Bottom,
        TopLeft, TopRight, BottomLeft, BottomRight
    };
    ResizeEdge resizeEdgeAt(const QPoint &pos) const;
    void updateResizeCursor(const QPoint &pos);

    QPushButton *m_pinButton = nullptr;
    QList<QPushButton *> m_suggestionCards;
    // 动态洞察卡（setInsights 渲染，追加在静态建议卡之后；刷新时先清空）。
    QList<QPushButton *> m_insightCards;
    // 今日简报入口卡（展示顺序保持在洞察卡之后，见 setInsights）。
    QPushButton *m_digestCard = nullptr;
    // 建议卡容器（静态 + 动态共用，动态卡在静态卡下方追加）。
    QVBoxLayout *m_suggestionsLayout = nullptr;
    InputBar *m_inputBar = nullptr;
    MessageList *m_messageList = nullptr;
    QStackedWidget *m_centerStack = nullptr;
    QWidget *m_welcomeView = nullptr;
    QPropertyAnimation *m_opacityAnimation = nullptr;
    QPoint m_rememberedPos;
    QPoint m_dragGlobalOffset;
    bool m_dragging = false;
    ResizeEdge m_resizeEdge = ResizeEdge::None;
    QRect m_resizeStartGeometry;
    QPoint m_resizeStartGlobalPos;
    bool m_resizing = false;
    bool m_pinned = false;
    void rebuildTopBarIcons();
    void togglePinned();

    static constexpr int kWindowWidth = 380;
    static constexpr int kWindowHeight = 640;
    static constexpr int kMinWidth = 320;
    static constexpr int kMinHeight = 480;
    static constexpr int kResizeMargin = 6;
    static constexpr int kAnimationMs = 150;
};

#endif // PIXIU_CHAT_WINDOW_H
