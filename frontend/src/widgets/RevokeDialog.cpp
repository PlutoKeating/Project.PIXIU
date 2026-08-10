#include "widgets/RevokeDialog.h"

#include "app/UiTokens.h"

#include <QHBoxLayout>
#include <QLabel>
#include <QPushButton>
#include <QShowEvent>
#include <QVBoxLayout>

RevokeDialog::RevokeDialog(QWidget *parent)
    : QDialog(parent)
{
    setWindowTitle(tr("确认解绑设备"));

    m_nameLabel = new QLabel(this);
    m_nameLabel->setObjectName(QStringLiteral("revokeNameLabel"));
    m_nameLabel->setWordWrap(true);

    QLabel *warningLabel = new QLabel(
        tr("解绑后该设备将退出共享域，记忆同步停止；可重新配对恢复。"), this);
    warningLabel->setWordWrap(true);

    QPushButton *cancelButton = new QPushButton(tr("取消"), this);
    cancelButton->setObjectName(QStringLiteral("revokeCancelButton"));
    cancelButton->setAccessibleName(tr("取消解绑"));
    cancelButton->setCursor(Qt::PointingHandCursor);
    QPushButton *confirmButton = new QPushButton(tr("解绑"), this);
    confirmButton->setObjectName(QStringLiteral("revokeConfirmButton"));
    confirmButton->setAccessibleName(tr("确认解绑"));
    confirmButton->setStyleSheet(ui::dangerButtonStyle());
    confirmButton->setCursor(Qt::PointingHandCursor);

    connect(cancelButton, &QPushButton::clicked, this, [this]() {
        emit cancelled();
        hide();
    });
    connect(confirmButton, &QPushButton::clicked, this, [this]() {
        emit confirmed();
        hide();
    });
    // 键盘可达：Esc / 窗口关闭视为取消。
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
    layout->addWidget(m_nameLabel);
    layout->addWidget(warningLabel);
    layout->addLayout(buttonRow);
}

void RevokeDialog::setPeerName(const QString &name)
{
    m_nameLabel->setText(tr("即将解绑设备：%1").arg(name));
}

void RevokeDialog::showEvent(QShowEvent *event)
{
    QDialog::showEvent(event);
    if (QPushButton *cancel =
            findChild<QPushButton *>(QStringLiteral("revokeCancelButton"))) {
        cancel->setFocus(Qt::OtherFocusReason);
    }
}

void RevokeDialog::showAndFocus()
{
    show();
    raise();
    activateWindow();
}
