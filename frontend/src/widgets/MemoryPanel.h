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
class PairDialog;
class RevokeDialog;

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
    // 切换到冲突 Tab（conflict_detected 事件到达且面板可见时使用）。
    void showConflictTab();

    // 更新冲突审计 Tab 内容（来自 GET /conflicts）。
    void setConflicts(const QJsonArray &conflicts);
    // 更新冲突 Tab 加载失败态（与空态区分，附带“重试”入口）。
    void setConflictsError(const QString &message);

    // 更新偏好历史 Tab 内容（来自 GET /preference/{id}/history）。
    void setPreferenceHistory(const QJsonObject &response);
    // 更新偏好历史 Tab 加载失败态。
    void setPreferenceHistoryError(const QString &message);

    // 更新同步 Tab 状态行（配对结果 / 后端契约状态）。
    void setSyncStatus(const QString &status, bool ok = false);

    // 更新同步 Tab 节点列表（来自 GET /sync/peers）。
    void setPeers(const QJsonArray &peers);

    // 更新同步 Tab 摘要（来自 GET /sync/status）。
    void setSyncSummary(const QJsonObject &status);

signals:
    // 用户请求加载指定偏好 ID 的历史。
    void historyRequested(const QString &preferenceId);
    // 用户请求重试加载冲突列表。
    void conflictRetryRequested();
    // 用户请求重试加载偏好历史（应用层以最近一次 ID 重发）。
    void preferenceRetryRequested();
    // 用户请求设备配对（载荷见 PairDialog::pairRequested）。
    void pairRequested(const QJsonObject &payload);
    // 用户请求刷新节点列表与同步状态。
    void syncRefreshRequested();
    // 用户已确认解绑指定设备（二次确认通过后发射）。
    void revokeConfirmed(const QString &peerId);

protected:
    // Esc 关闭面板（键盘可达）。
    void keyPressEvent(QKeyEvent *event) override;

private:
    QWidget *createConflictTab();
    QWidget *createPreferenceTab();
    QWidget *createSyncTab();

    QTabWidget *m_tabs = nullptr;
    QListWidget *m_conflictList = nullptr;
    QLabel *m_conflictEmptyLabel = nullptr;
    QLabel *m_conflictErrorLabel = nullptr;
    QPushButton *m_conflictRetryButton = nullptr;
    QLineEdit *m_prefIdInput = nullptr;
    QListWidget *m_prefHistoryList = nullptr;
    QLabel *m_prefHeaderLabel = nullptr;
    QLabel *m_prefEmptyLabel = nullptr;
    QLabel *m_prefErrorLabel = nullptr;
    QPushButton *m_prefRetryButton = nullptr;
    QLabel *m_syncStatusLabel = nullptr;
    QLabel *m_syncSummaryLabel = nullptr;
    QLabel *m_syncEmptyLabel = nullptr;
    QListWidget *m_peerList = nullptr;
    PairDialog *m_pairDialog = nullptr;
    RevokeDialog *m_revokeDialog = nullptr;
    QString m_pendingRevokePeerId;

    void requestRevoke(const QString &peerId, const QString &peerName);
};

#endif // PIXIU_MEMORY_PANEL_H
