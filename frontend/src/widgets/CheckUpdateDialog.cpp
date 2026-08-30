#include "widgets/CheckUpdateDialog.h"

#include "app/UiTokens.h"

#include <QCoreApplication>
#include <QHBoxLayout>
#include <QLabel>
#include <QPushButton>
#include <QVBoxLayout>

CheckUpdateDialog::CheckUpdateDialog(QWidget *parent)
    : QDialog(parent)
{
    setObjectName(QStringLiteral("checkUpdateDialog"));
    setWindowTitle(tr("检查更新"));
    // 非模态：与设置/遗忘等弹窗一致，关闭只关本弹窗。
    resize(400, 220);
    setMinimumSize(360, 200);

    QLabel *titleLabel = new QLabel(tr("检查更新"), this);
    titleLabel->setObjectName(QStringLiteral("checkUpdateTitleLabel"));
    titleLabel->setFont(ui::Font::title());

    m_bodyLabel = new QLabel(
        tr("当前版本 %1。请从官方渠道获取最新版本，通过安装包直接升级；"
           "升级将保留您的记忆与配置。")
            .arg(QCoreApplication::applicationVersion()),
        this);
    m_bodyLabel->setObjectName(QStringLiteral("checkUpdateBodyLabel"));
    m_bodyLabel->setWordWrap(true);

    QPushButton *closeButton = new QPushButton(tr("知道了"), this);
    closeButton->setObjectName(QStringLiteral("checkUpdateCloseButton"));
    closeButton->setAccessibleName(tr("知道了"));
    closeButton->setCursor(Qt::PointingHandCursor);
    closeButton->setDefault(true);
    connect(closeButton, &QPushButton::clicked, this, &QDialog::hide);

    QHBoxLayout *buttonRow = new QHBoxLayout();
    buttonRow->addStretch(1);
    buttonRow->addWidget(closeButton);

    QVBoxLayout *layout = new QVBoxLayout(this);
    layout->addWidget(titleLabel);
    layout->addWidget(m_bodyLabel);
    layout->addStretch(1);
    layout->addLayout(buttonRow);
}

void CheckUpdateDialog::showAndFocus()
{
    show();
    raise();
    activateWindow();
}
