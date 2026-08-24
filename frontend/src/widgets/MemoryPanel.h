#ifndef PIXIU_MEMORY_PANEL_H
#define PIXIU_MEMORY_PANEL_H

#include <QJsonArray>
#include <QJsonObject>
#include <QWidget>

class QLabel;
class QLineEdit;
class QListWidget;
class QComboBox;
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
    // 切换到同步 Tab（chip/菜单“同步面板”入口使用）。
    void showSyncTab();

    // 更新冲突审计 Tab 内容（来自 GET /conflicts）。
    void setConflicts(const QJsonArray &conflicts);
    // 切换冲突 Tab 加载中态（与空态/失败态互斥）。
    void setConflictsLoading();
    // 更新冲突 Tab 加载失败态（与空态区分，附带“重试”入口）。
    void setConflictsError(const QString &message);

    // 更新偏好历史 Tab 内容（来自 GET /preference/{id}/history）。
    void setPreferenceHistory(const QJsonObject &response);
    // 切换偏好历史 Tab 加载中态。
    void setPreferenceHistoryLoading();
    // 更新偏好历史 Tab 加载失败态。
    void setPreferenceHistoryError(const QString &message);
    // 偏好提取结果反馈（成功：条数；失败：错误信息）。
    void setPreferenceExtractResult(int count);
    void setPreferenceExtractError(const QString &message);

    // 更新偏好下拉列表（来自 GET /preferences）。
    void setPreferenceList(const QJsonArray &preferences);

    // 展示 /sync/token 返回的本机配对令牌（转发到配对对话框）。
    void showPairingToken(const QJsonObject &response);
    // 配对令牌生成失败反馈。
    void showPairingTokenError(const QString &message);

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
    // 用户请求从最近录入的证据提取偏好（POST /preference/extract）。
    void extractPreferencesRequested();
    // 用户请求刷新偏好列表（GET /preferences）。
    void preferencesRefreshRequested();
    // 用户请求生成本机配对令牌（POST /sync/token）。
    void pairingTokenRequested(const QJsonObject &payload);
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
    QComboBox *m_prefListCombo = nullptr;
    QListWidget *m_prefHistoryList = nullptr;
    QLabel *m_prefHeaderLabel = nullptr;
    QLabel *m_prefEmptyLabel = nullptr;
    QLabel *m_prefErrorLabel = nullptr;
    QLabel *m_prefExtractLabel = nullptr;
    QPushButton *m_prefExtractButton = nullptr;
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
