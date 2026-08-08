#ifndef PIXIU_MEMORY_PANEL_H
#define PIXIU_MEMORY_PANEL_H

#include <QJsonArray>
#include <QJsonObject>
#include <QWidget>

class QLabel;
class QLineEdit;
class QListWidget;
class QKeyEvent;
class QPushButton;
class QTabWidget;

// 记忆管理面板：偏好 / 冲突 / 同步 三个 Tab。
//
// 本阶段提供面板壳与 Tab 状态；各 Tab 内容由后续 feature 填充
// （偏好历史、冲突审计、设备配对/同步状态）。
class MemoryPanel : public QWidget
{
    Q_OBJECT

public:
    explicit MemoryPanel(QWidget *parent = nullptr);

    // 显示并前置。
    void showAndFocus();

    // 更新冲突审计 Tab 内容（来自 GET /conflicts）。
    void setConflicts(const QJsonArray &conflicts);

    // 更新偏好历史 Tab 内容（来自 GET /preference/{id}/history）。
    void setPreferenceHistory(const QJsonObject &response);

signals:
    // 用户请求加载指定偏好 ID 的历史。
    void historyRequested(const QString &preferenceId);

protected:
    // Esc 关闭面板（键盘可达）。
    void keyPressEvent(QKeyEvent *event) override;

private:
    QWidget *createPlaceholderTab(const QString &title, const QString &description) const;
    QWidget *createConflictTab();
    QWidget *createPreferenceTab();

    QTabWidget *m_tabs = nullptr;
    QListWidget *m_conflictList = nullptr;
    QLabel *m_conflictEmptyLabel = nullptr;
    QLineEdit *m_prefIdInput = nullptr;
    QListWidget *m_prefHistoryList = nullptr;
    QLabel *m_prefHeaderLabel = nullptr;
    QLabel *m_prefEmptyLabel = nullptr;
};

#endif // PIXIU_MEMORY_PANEL_H
