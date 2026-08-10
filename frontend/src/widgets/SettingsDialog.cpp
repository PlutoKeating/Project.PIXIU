#include "widgets/SettingsDialog.h"

#include "app/UiTokens.h"

#include <QComboBox>
#include <QCoreApplication>
#include <QFormLayout>
#include <QHBoxLayout>
#include <QLabel>
#include <QKeySequenceEdit>
#include <QPushButton>
#include <QVBoxLayout>

SettingsDialog::SettingsDialog(QWidget *parent)
    : QDialog(parent)
{
    setWindowTitle(tr("设置"));
    setModal(true);
    // 固定高度会裁剪英文长提示（快捷键说明等 i18n 长文案）；改为默认尺寸 +
    // 最小尺寸，内容超出时随 sizeHint 增高（中文保持 400x330 不变化）。
    resize(400, 330);
    setMinimumSize(400, 330);

    QLabel *titleLabel = new QLabel(tr("PIXIU 设置"), this);
    titleLabel->setObjectName(QStringLiteral("settingsTitleLabel"));
    titleLabel->setFont(ui::Font::title());

    m_languageCombo = new QComboBox(this);
    m_languageCombo->setObjectName(QStringLiteral("languageCombo"));
    m_languageCombo->setAccessibleName(tr("界面语言"));
    m_languageCombo->addItem(tr("跟随系统"), QStringLiteral("system"));
    m_languageCombo->addItem(tr("中文"), QStringLiteral("zh_CN"));
    m_languageCombo->addItem(tr("English"), QStringLiteral("en_US"));

    QFormLayout *formLayout = new QFormLayout();
    formLayout->addRow(tr("界面语言"), m_languageCombo);

    m_shortcutEdit = new QKeySequenceEdit(this);
    m_shortcutEdit->setObjectName(QStringLiteral("shortcutEdit"));
    m_shortcutEdit->setAccessibleName(tr("全局快捷键"));
    m_shortcutEdit->setKeySequence(
        QKeySequence(QStringLiteral("Ctrl+Alt+P")));
    formLayout->addRow(tr("全局快捷键"), m_shortcutEdit);

    QLabel *hintLabel = new QLabel(tr("语言偏好将在下次启动时生效。"), this);
    hintLabel->setObjectName(QStringLiteral("languageHint"));
    hintLabel->setWordWrap(true);

    QLabel *shortcutHint = new QLabel(
        tr("快捷键需包含 Ctrl / Alt / Meta 修饰键；修改后立即生效。"), this);
    shortcutHint->setObjectName(QStringLiteral("shortcutHint"));
    shortcutHint->setWordWrap(true);

    QLabel *aboutLabel = new QLabel(tr("PIXIU 貔貅 · 记忆管家"), this);
    QLabel *versionLabel = new QLabel(
        tr("版本 %1").arg(QCoreApplication::applicationVersion()), this);
    versionLabel->setObjectName(QStringLiteral("versionLabel"));

    m_okButton = new QPushButton(tr("确定"), this);
    m_okButton->setObjectName(QStringLiteral("settingsOkButton"));
    m_okButton->setAccessibleName(tr("保存设置"));
    m_okButton->setDefault(true);
    m_okButton->setCursor(Qt::PointingHandCursor);
    connect(m_okButton, &QPushButton::clicked, this, &QDialog::accept);

    QPushButton *cancelButton = new QPushButton(tr("取消"), this);
    cancelButton->setObjectName(QStringLiteral("settingsCancelButton"));
    cancelButton->setAccessibleName(tr("取消设置"));
    cancelButton->setCursor(Qt::PointingHandCursor);
    connect(cancelButton, &QPushButton::clicked, this, &QDialog::reject);
    // 键盘可达：Esc / 窗口关闭（QDialog::reject）统一视为取消。
    connect(this, &QDialog::rejected, this, &SettingsDialog::cancelled);

    QHBoxLayout *buttonRow = new QHBoxLayout();
    buttonRow->addStretch(1);
    buttonRow->addWidget(cancelButton);
    buttonRow->addWidget(m_okButton);

    QVBoxLayout *layout = new QVBoxLayout(this);
    layout->addWidget(titleLabel);
    layout->addLayout(formLayout);
    layout->addWidget(hintLabel);
    layout->addWidget(shortcutHint);
    layout->addStretch(1);
    layout->addWidget(aboutLabel);
    layout->addWidget(versionLabel);
    layout->addLayout(buttonRow);

    connect(m_shortcutEdit, &QKeySequenceEdit::keySequenceChanged,
            this, &SettingsDialog::updateOkEnabled);
    updateOkEnabled();
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

QKeySequence SettingsDialog::selectedShortcut() const
{
    return m_shortcutEdit->keySequence();
}

void SettingsDialog::setShortcut(const QKeySequence &sequence)
{
    m_shortcutEdit->setKeySequence(
        sequence.isEmpty()
            ? QKeySequence(QStringLiteral("Ctrl+Alt+P"))
            : sequence);
}

void SettingsDialog::updateOkEnabled()
{
    // 全局快捷键必须非空且含修饰键，避免裸键劫持桌面输入。
    const QKeySequence sequence = m_shortcutEdit->keySequence();
    const QString portable =
        sequence.toString(QKeySequence::PortableText);
    const bool valid =
        !sequence.isEmpty()
        && (portable.contains(QLatin1String("Ctrl"))
            || portable.contains(QLatin1String("Alt"))
            || portable.contains(QLatin1String("Meta")));
    m_okButton->setEnabled(valid);
}
