#pragma once
#include <QWidget>
#include "AgentEvidence.h"

class BackendTransport;
class QLineEdit;
class QComboBox;
class QPushButton;
class QLabel;
class QPlainTextEdit;
class QListWidget;
class QCheckBox;
class QTabWidget;

namespace pixiu {
class MemoryAudit;
// An embedded workspace: no application, tray, window lifecycle or Agent loop.
class MemoryWorkspace : public QWidget
{
    Q_OBJECT
public:
    explicit MemoryWorkspace(QWidget *parent = nullptr, BackendTransport *transport = nullptr);
    bool hasPendingOperation() const { return m_request != 0 || m_evidenceBusy; }
    // Only accepts parsed Runtime references, never IDs extracted from model text.
    bool showAgentSources(const AgentEvidenceResult &result, const QString &scope);
    void clearAgentSources();
private:
    void search();
    void clearResult();
    void clearEvidence();
    BackendTransport *m_transport;
    MemoryAudit *m_audit;
    QLineEdit *m_query;
    QComboBox *m_scope;
    QTabWidget *m_tabs;
    QPushButton *m_search;
    QPushButton *m_edit;
    QString m_knowledge;
    QLabel *m_status;
    QPlainTextEdit *m_answer;
    QListWidget *m_sources;
    QLabel *m_detailMeta;
    QPlainTextEdit *m_detail;
    QCheckBox *m_showRaw;
    QString m_evidenceText;
    QString m_evidenceRaw;
    quint64 m_request = 0;
    QString m_evidence;
    QString m_expectedEvidenceScope;
    bool m_evidenceBusy = false;
    bool m_agentSources = false;
};
}
