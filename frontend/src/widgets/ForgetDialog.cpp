#include "widgets/ForgetDialog.h"

#include "app/UiTokens.h"

#include <QCoreApplication>
#include <QHBoxLayout>
#include <QLabel>
#include <QPushButton>
#include <QStringList>
#include <QVBoxLayout>

namespace {
QString buildSummary(const QJsonArray &targets, const QJsonObject &cascade)
{
    QStringList names;
    for (const QJsonValue &value : targets) {
        const QJsonObject obj = value.toObject();
        const QString title = obj.value(QStringLiteral("title")).toString();
        const QString type = obj.value(QStringLiteral("type")).toString();
        if (!title.isEmpty()) {
            names << title;
        } else if (!type.isEmpty()) {
            names << type;
        }
    }

    QString summary;
    if (names.isEmpty()) {
        summary = QCoreApplication::translate(
                      "ForgetDialog", "即将遗忘 %1 个目标。")
                      .arg(targets.size());
    } else {
        summary = QCoreApplication::translate("ForgetDialog", "即将遗忘：%1。")
                      .arg(names.join(QStringLiteral("；")));
    }

    const int evidenceCount = cascade.value(QStringLiteral("evidence_count")).toInt();
    const int relationCount = cascade.value(QStringLiteral("relation_count")).toInt();
    if (evidenceCount > 0 || relationCount > 0) {
        summary += QCoreApplication::translate(
                       "ForgetDialog", "\n将级联清理：证据 %1 条 · 关系 %2 条。")
                       .arg(evidenceCount)
                       .arg(relationCount);
    }
    summary += QCoreApplication::translate("ForgetDialog", "\n此操作不可撤销。");
    return summary;
}
}

ForgetDialog::ForgetDialog(QWidget *parent)
    : QDialog(parent)
{
    setWindowTitle(tr("确认遗忘"));

    m_summaryLabel = new QLabel(this);
    m_summaryLabel->setWordWrap(true);

    QPushButton *cancelButton = new QPushButton(tr("取消"), this);
    QPushButton *confirmButton = new QPushButton(tr("确认遗忘"), this);
    confirmButton->setObjectName(QStringLiteral("dangerConfirmButton"));
    confirmButton->setStyleSheet(ui::dangerButtonStyle());

    connect(cancelButton, &QPushButton::clicked, this, [this]() {
        emit cancelled();
        hide();
    });
    connect(confirmButton, &QPushButton::clicked, this, [this]() {
        emit confirmed();
        hide();
    });
    // 键盘可达：Esc / 窗口关闭（QDialog::reject）同样视为取消，避免
    // ForgetController 残留待确认指令。
    connect(this, &QDialog::rejected, this, [this]() {
        emit cancelled();
    });
    // 危险操作默认聚焦“取消”，Enter 不误触确认。
    cancelButton->setDefault(true);

    QHBoxLayout *buttonRow = new QHBoxLayout();
    buttonRow->addStretch(1);
    buttonRow->addWidget(cancelButton);
    buttonRow->addWidget(confirmButton);

    QVBoxLayout *layout = new QVBoxLayout(this);
    layout->addWidget(m_summaryLabel);
    layout->addLayout(buttonRow);
}

void ForgetDialog::setForgetTargets(const QJsonArray &targets, const QJsonObject &cascade)
{
    m_summaryLabel->setText(buildSummary(targets, cascade));
}
