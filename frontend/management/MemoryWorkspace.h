#pragma once
#include <QWidget>

class BackendTransport;
class QLineEdit;
class QComboBox;
class QPushButton;
class QLabel;
class QPlainTextEdit;
class QListWidget;

namespace pixiu {
class MemoryAudit;
// An embedded workspace: no application, tray, window lifecycle or Agent loop.
class MemoryWorkspace : public QWidget
{
    Q_OBJECT
public:
    explicit MemoryWorkspace(QWidget *parent = nullptr, BackendTransport *transport = nullptr);
private:
    void search();
    void clearResult();
    BackendTransport *m_transport;
    MemoryAudit *m_audit;
    QLineEdit *m_query;
    QComboBox *m_scope;
    QPushButton *m_search;
    QPushButton *m_edit;
    QString m_knowledge;
    QLabel *m_status;
    QPlainTextEdit *m_answer;
    QListWidget *m_sources;
    QLabel *m_detailMeta;
    QPlainTextEdit *m_detail;
    quint64 m_request = 0;
    QString m_evidence;
    bool m_evidenceBusy = false;
};
}
