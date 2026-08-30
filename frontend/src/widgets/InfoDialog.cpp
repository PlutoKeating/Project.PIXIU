#include "widgets/InfoDialog.h"

#include "app/UiTokens.h"

#include <QHBoxLayout>
#include <QLabel>
#include <QPushButton>
#include <QTextBrowser>
#include <QVBoxLayout>

InfoDialog::InfoDialog(const QString &title, const QString &body,
                       QWidget *parent)
    : QDialog(parent)
{
    setObjectName(QStringLiteral("infoDialog"));
    setWindowTitle(title);
    // 非模态：与设置/遗忘/监控中心等弹窗一致，关闭只关本弹窗，不阻塞聊天。
    resize(420, 360);
    setMinimumSize(360, 280);

    QLabel *titleLabel = new QLabel(title, this);
    titleLabel->setObjectName(QStringLiteral("infoTitleLabel"));
    titleLabel->setFont(ui::Font::title());
    titleLabel->setWordWrap(true);

    m_textBrowser = new QTextBrowser(this);
    m_textBrowser->setObjectName(QStringLiteral("infoTextBrowser"));
    // QTextBrowser 默认只读；用纯文本渲染避免 HTML 转义/换行折叠问题
    //（正文为调用方传入的参赛语境文案，多段以空行分隔）。
    m_textBrowser->setPlainText(body);

    QPushButton *closeButton = new QPushButton(tr("关闭"), this);
    closeButton->setObjectName(QStringLiteral("infoCloseButton"));
    closeButton->setAccessibleName(tr("关闭"));
    closeButton->setDefault(true);
    closeButton->setCursor(Qt::PointingHandCursor);
    connect(closeButton, &QPushButton::clicked, this, &QDialog::hide);

    QHBoxLayout *buttonRow = new QHBoxLayout();
    buttonRow->addStretch(1);
    buttonRow->addWidget(closeButton);

    QVBoxLayout *layout = new QVBoxLayout(this);
    layout->addWidget(titleLabel);
    layout->addWidget(m_textBrowser, 1);
    layout->addLayout(buttonRow);
}

void InfoDialog::showAndFocus()
{
    show();
    raise();
    activateWindow();
}
