#pragma once
#include <QWidget>
#include <QStringList>
class BackendTransport;
class QComboBox;
class QPushButton;
class QLabel;
class QListWidget;
class QPlainTextEdit;
class QTimer;
namespace pixiu {
class MemoryAudit : public QWidget
{
    Q_OBJECT
public:
    explicit MemoryAudit(QWidget *parent, BackendTransport *transport = nullptr);
    void setEvidenceIds(const QStringList &ids);
    void notifyDataChanged();
    bool hasPendingOperation() const { return m_pending != Pending::None; }
protected:
    void showEvent(QShowEvent *event) override;
private:
    enum class Pending { None, Preferences, History, Conflicts, Extract };
    void refresh(bool preserveSelection = false);
    void scheduleRefresh();
    void restoreSelection();
    void updateControls();
    BackendTransport *m_transport;
    QComboBox *m_mode;
    QComboBox *m_scope;
    QPushButton *m_refresh;
    QPushButton *m_extract;
    QLabel *m_status;
    QListWidget *m_records;
    QPlainTextEdit *m_details;
    QStringList m_evidenceIds;
    QString m_historyId;
    QString m_restoreSelection;
    QTimer *m_refreshTimer;
    bool m_refreshNeeded = false;
    Pending m_pending = Pending::None;
};
}
