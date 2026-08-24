#include "widgets/EvidenceDetailDialog.h"

#include "app/UiTokens.h"

#include <QJsonDocument>
#include <QJsonObject>
#include <QLabel>
#include <QPlainTextEdit>
#include <QPushButton>
#include <QStringList>
#include <QVBoxLayout>

EvidenceDetailDialog::EvidenceDetailDialog(QWidget *parent)
    : QDialog(parent)
{
    setWindowTitle(tr("证据详情"));
    setModal(false);
    resize(420, 360);
    setMinimumSize(320, 260);

    m_titleLabel = new QLabel(this);
    m_titleLabel->setObjectName(QStringLiteral("evidenceDetailTitle"));
    m_titleLabel->setFont(ui::Font::title());
    m_titleLabel->setWordWrap(true);

    m_metaLabel = new QLabel(this);
    m_metaLabel->setObjectName(QStringLiteral("evidenceDetailMeta"));
    m_metaLabel->setStyleSheet(ui::textStyle(ui::Role::Muted));
    m_metaLabel->setWordWrap(true);

    m_rawView = new QPlainTextEdit(this);
    m_rawView->setObjectName(QStringLiteral("evidenceDetailView"));
    m_rawView->setReadOnly(true);
    m_rawView->setLineWrapMode(QPlainTextEdit::WidgetWidth);

    QPushButton *closeButton = new QPushButton(tr("关闭"), this);
    closeButton->setObjectName(QStringLiteral("evidenceDetailCloseButton"));
    closeButton->setDefault(true);
    closeButton->setCursor(Qt::PointingHandCursor);
    connect(closeButton, &QPushButton::clicked, this, &QDialog::hide);

    QVBoxLayout *layout = new QVBoxLayout(this);
    layout->addWidget(m_titleLabel);
    layout->addWidget(m_metaLabel);
    layout->addWidget(m_rawView, 1);
    layout->addWidget(closeButton, 0, Qt::AlignRight);

    showLoading(QString());
}

void EvidenceDetailDialog::showLoading(const QString &evidenceId)
{
    setWindowTitle(evidenceId.isEmpty()
                       ? tr("证据详情")
                       : tr("证据详情 · %1").arg(evidenceId));
    m_titleLabel->setText(tr("正在加载证据…"));
    m_metaLabel->clear();
    m_rawView->clear();
    show();
    raise();
    activateWindow();
}

void EvidenceDetailDialog::setEvidence(const QJsonObject &evidence)
{
    const QString id = evidence.value(QStringLiteral("id")).toString();
    setWindowTitle(tr("证据详情 · %1").arg(id));

    QStringList meta;
    meta << tr("来源：%1")
                .arg(evidence.value(QStringLiteral("source_type")).toString());
    meta << tr("质量评分：%1")
                .arg(evidence.value(QStringLiteral("quality_score")).toDouble(), 0, 'f', 2);
    meta << tr("敏感度：%1")
                .arg(evidence.value(QStringLiteral("sensitivity")).toInt());
    meta << tr("范围：%1").arg(evidence.value(QStringLiteral("scope")).toString());
    m_titleLabel->setText(
        evidence.value(QStringLiteral("raw")).toObject()
            .value(QStringLiteral("title"))
            .toString(tr("（未命名）")));
    m_metaLabel->setText(meta.join(QStringLiteral(" · ")));

    const QJsonValue raw = evidence.value(QStringLiteral("raw"));
    m_rawView->setPlainText(
        QJsonDocument(raw.toObject()).toJson(QJsonDocument::Indented));
}

void EvidenceDetailDialog::setError(const QString &message)
{
    m_titleLabel->setText(tr("加载失败"));
    m_metaLabel->setText(message);
    m_metaLabel->setStyleSheet(ui::textStyle(ui::Role::Error));
}
