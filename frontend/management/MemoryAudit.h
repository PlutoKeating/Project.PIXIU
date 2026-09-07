#pragma once
#include <QWidget>
#include <QStringList>
class BackendTransport;
class QComboBox;
class QPushButton;
class QLabel;
class QListWidget;
class QPlainTextEdit;
namespace pixiu {
class MemoryAudit : public QWidget
{
    Q_OBJECT
public:
    explicit MemoryAudit(QWidget *parent, BackendTransport *transport = nullptr);
    void setEvidenceIds(const QStringList &ids);
private:
    enum class Pending { None, Preferences, History, Conflicts, Extract };
    void refresh();
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
    Pending m_pending = Pending::None;
};
}
