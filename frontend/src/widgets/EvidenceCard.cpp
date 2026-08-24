#include "widgets/EvidenceCard.h"

#include <QHBoxLayout>
#include <QLabel>
#include <QMouseEvent>
#include <QVBoxLayout>

EvidenceCard::EvidenceCard(const QString &evidenceId,
                           double confidence,
                           int latencyMs,
                           QWidget *parent)
    : QFrame(parent)
    , m_evidenceId(evidenceId)
{
    setObjectName(QStringLiteral("evidenceCard"));
    setCursor(Qt::PointingHandCursor);
    setToolTip(tr("点击查看原文"));

    QLabel *title = new QLabel(tr("📄 原始证据"), this);
    title->setObjectName(QStringLiteral("evidenceTitle"));

    QString meta = tr("证据 %1 · 置信度 %2 · 延迟 %3ms")
                       .arg(m_evidenceId,
                            QString::number(confidence, 'f', 2))
                       .arg(latencyMs);
    QLabel *metaLabel = new QLabel(meta, this);
    metaLabel->setObjectName(QStringLiteral("evidenceMeta"));

    QLabel *action = new QLabel(tr("查看原文 →"), this);
    action->setObjectName(QStringLiteral("evidenceAction"));

    QHBoxLayout *top = new QHBoxLayout();
    top->setContentsMargins(0, 0, 0, 0);
    top->addWidget(title);
    top->addStretch(1);
    top->addWidget(action);

    QVBoxLayout *layout = new QVBoxLayout(this);
    layout->setContentsMargins(10, 8, 10, 8);
    layout->setSpacing(3);
    layout->addLayout(top);
    layout->addWidget(metaLabel);
}

void EvidenceCard::mousePressEvent(QMouseEvent *event)
{
    if (event->button() == Qt::LeftButton) {
        emit evidenceClicked(m_evidenceId);
        event->accept();
        return;
    }
    QFrame::mousePressEvent(event);
}
