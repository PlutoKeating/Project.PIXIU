#pragma once
#include <QDialog>
#include <QJsonObject>
class BackendTransport;
class QLineEdit;
class QPlainTextEdit;
class QLabel;
class QPushButton;
class QCheckBox;
namespace pixiu {
class MemoryEditDialog : public QDialog
{
    Q_OBJECT
public:
    explicit MemoryEditDialog(QWidget *parent, BackendTransport *transport = nullptr);
    void openMemory(const QString &id, const QString &scope);
    void reject() override;
signals:
    void memoryUpdated();
private:
    void refresh();
    void submit();
    void updateControls();
    QJsonObject editedBody(bool *valid = nullptr) const;
    bool hasChanges() const;
    enum class Pending { None, Read, Save };
    Pending m_pending = Pending::None;
    BackendTransport *m_transport;
    QLineEdit *m_title;
    QPlainTextEdit *m_body;
    QLabel *m_bodyLabel;
    QCheckBox *m_structured;
    QLabel *m_status;
    QLabel *m_target;
    QPushButton *m_save;
    QPushButton *m_reload;
    QPushButton *m_close;
    QString m_id, m_scope, m_key;
    QJsonObject m_original, m_lastPayload, m_draftBody;
    int m_version = 0;
    bool m_stale = false;
    bool m_textMode = false;
};
}
