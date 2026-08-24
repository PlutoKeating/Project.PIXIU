#ifndef PIXIU_EVIDENCE_DETAIL_DIALOG_H
#define PIXIU_EVIDENCE_DETAIL_DIALOG_H

#include <QDialog>
#include <QJsonObject>

// 证据详情对话框：展示 GET /evidence/{id} 返回的原始证据内容。
class EvidenceDetailDialog : public QDialog
{
    Q_OBJECT

public:
    explicit EvidenceDetailDialog(QWidget *parent = nullptr);

    // 填充证据详情并展示；加载中/加载失败由 setStates 控制。
    void showLoading(const QString &evidenceId);
    void setEvidence(const QJsonObject &evidence);
    void setError(const QString &message);

private:
    class QLabel *m_titleLabel = nullptr;
    class QLabel *m_metaLabel = nullptr;
    class QPlainTextEdit *m_rawView = nullptr;
};

#endif // PIXIU_EVIDENCE_DETAIL_DIALOG_H
