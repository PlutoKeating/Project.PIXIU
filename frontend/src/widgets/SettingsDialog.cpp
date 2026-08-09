#include "widgets/SettingsDialog.h"

#include <QComboBox>
#include <QCoreApplication>
#include <QFont>
#include <QFormLayout>
#include <QHBoxLayout>
#include <QLabel>
#include <QPushButton>
#include <QVBoxLayout>

SettingsDialog::SettingsDialog(QWidget *parent)
    : QDialog(parent)
{
    setWindowTitle(tr("设置"));
    setModal(true);
    setFixedSize(360, 250);

    QLabel *titleLabel = new QLabel(tr("PIXIU 设置"), this);
    QFont titleFont = titleLabel->font();
    titleFont.setPixelSize(14);
    titleFont.setBold(true);
    titleLabel->setFont(titleFont);

    m_languageCombo = new QComboBox(this);
    m_languageCombo->setObjectName(QStringLiteral("languageCombo"));
    m_languageCombo->setAccessibleName(tr("界面语言"));
    m_languageCombo->addItem(tr("跟随系统"), QStringLiteral("system"));
    m_languageCombo->addItem(tr("中文"), QStringLiteral("zh_CN"));
    m_languageCombo->addItem(tr("English"), QStringLiteral("en_US"));

    QFormLayout *formLayout = new QFormLayout();
    formLayout->addRow(tr("界面语言"), m_languageCombo);

    QLabel *hintLabel = new QLabel(tr("语言偏好将在下次启动时生效。"), this);
    hintLabel->setObjectName(QStringLiteral("languageHint"));
    hintLabel->setWordWrap(true);

    QLabel *aboutLabel = new QLabel(tr("PIXIU 貔貅 · 记忆管家"), this);
    QLabel *versionLabel = new QLabel(
        tr("版本 %1").arg(QCoreApplication::applicationVersion()), this);
    versionLabel->setObjectName(QStringLiteral("versionLabel"));

    QPushButton *okButton = new QPushButton(tr("确定"), this);
    okButton->setObjectName(QStringLiteral("settingsOkButton"));
    okButton->setAccessibleName(tr("保存设置"));
    okButton->setDefault(true);
    connect(okButton, &QPushButton::clicked, this, &QDialog::accept);

    QPushButton *cancelButton = new QPushButton(tr("取消"), this);
    cancelButton->setObjectName(QStringLiteral("settingsCancelButton"));
    cancelButton->setAccessibleName(tr("取消设置"));
    connect(cancelButton, &QPushButton::clicked, this, &QDialog::reject);
    // 键盘可达：Esc / 窗口关闭（QDialog::reject）统一视为取消。
    connect(this, &QDialog::rejected, this, &SettingsDialog::cancelled);

    QHBoxLayout *buttonRow = new QHBoxLayout();
    buttonRow->addStretch(1);
    buttonRow->addWidget(cancelButton);
    buttonRow->addWidget(okButton);

    QVBoxLayout *layout = new QVBoxLayout(this);
    layout->addWidget(titleLabel);
    layout->addLayout(formLayout);
    layout->addWidget(hintLabel);
    layout->addStretch(1);
    layout->addWidget(aboutLabel);
    layout->addWidget(versionLabel);
    layout->addLayout(buttonRow);
}

void SettingsDialog::showAndFocus()
{
    show();
    raise();
    activateWindow();
    m_languageCombo->setFocus();
}

QString SettingsDialog::selectedLanguage() const
{
    return m_languageCombo->currentData().toString();
}

void SettingsDialog::setLanguage(const QString &language)
{
    const int index = m_languageCombo->findData(language);
    m_languageCombo->setCurrentIndex(index >= 0 ? index : 0);
}
