#ifndef PIXIU_EVIDENCE_CARD_H
#define PIXIU_EVIDENCE_CARD_H

#include <QFrame>
#include <QString>

// 检索结果证据卡：展示证据来源、置信度与延迟，点击回溯原文。
//
// 后端证据详情端点尚缺，点击仅发射 evidenceClicked，由应用层决定展示方式。
class EvidenceCard : public QFrame
{
    Q_OBJECT

public:
    explicit EvidenceCard(const QString &evidenceId,
                          double confidence,
                          int latencyMs,
                          QWidget *parent = nullptr);

signals:
    void evidenceClicked(const QString &evidenceId);

protected:
    void mousePressEvent(QMouseEvent *event) override;

private:
    QString m_evidenceId;
};

#endif // PIXIU_EVIDENCE_CARD_H
