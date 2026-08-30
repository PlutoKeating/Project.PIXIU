#include "widgets/SettingsDialog.h"

#include "app/UiTokens.h"

#include <QComboBox>
#include <QCoreApplication>
#include <QFormLayout>
#include <QGridLayout>
#include <QHBoxLayout>
#include <QLabel>
#include <QKeySequenceEdit>
#include <QPushButton>
#include <QVBoxLayout>

SettingsDialog::SettingsDialog(QWidget *parent)
    : QDialog(parent)
{
    setWindowTitle(tr("设置"));
    // 非模态：与记忆面板/录入/配对等功能弹窗一致。设置窗与聊天框相互独立，
    // 关闭设置弹窗（含窗口“×”）只关闭该弹窗本身，不得因模态残留导致
    // 聊天框无法继续交互（kylin-wlcom 上实测模态弹窗被 WM 关闭后应用会
    // 进入输入卡死）。
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

    // 监控掌控层入口：打开监控中心面板（数据源开关/目录/活动记录）。
    m_monitorButton = new QPushButton(tr("监控中心…"), this);
    m_monitorButton->setObjectName(QStringLiteral("openMonitorCenterButton"));
    m_monitorButton->setAccessibleName(tr("打开监控中心"));
    m_monitorButton->setCursor(Qt::PointingHandCursor);
    connect(m_monitorButton, &QPushButton::clicked,
            this, &SettingsDialog::monitorCenterRequested);

    QLabel *aboutLabel = new QLabel(tr("PIXIU 貔貅 · 记忆管家"), this);
    QLabel *versionLabel = new QLabel(
        tr("版本 %1").arg(QCoreApplication::applicationVersion()), this);
    versionLabel->setObjectName(QStringLiteral("versionLabel"));

    // 关于与法律四入口：检查更新 / 关于 PIXIU / 服务条款 / 隐私政策。
    // 布局用 2×2 grid 而非单行：400px 窄窗下单行四按钮总宽超出内容区会
    // 裁剪（按钮文字不可压缩），两行两列保证任何窗口宽度都不裁剪。
    QPushButton *checkUpdateButton = new QPushButton(tr("检查更新…"), this);
    checkUpdateButton->setObjectName(QStringLiteral("checkUpdateButton"));
    checkUpdateButton->setAccessibleName(tr("打开检查更新"));
    checkUpdateButton->setCursor(Qt::PointingHandCursor);
    connect(checkUpdateButton, &QPushButton::clicked,
            this, &SettingsDialog::checkUpdateRequested);

    QPushButton *aboutUsButton = new QPushButton(tr("关于 PIXIU"), this);
    aboutUsButton->setObjectName(QStringLiteral("aboutUsButton"));
    aboutUsButton->setAccessibleName(tr("打开关于页面"));
    aboutUsButton->setCursor(Qt::PointingHandCursor);
    connect(aboutUsButton, &QPushButton::clicked,
            this, &SettingsDialog::aboutUsRequested);

    QPushButton *termsButton = new QPushButton(tr("服务条款"), this);
    termsButton->setObjectName(QStringLiteral("termsButton"));
    termsButton->setAccessibleName(tr("打开服务条款"));
    termsButton->setCursor(Qt::PointingHandCursor);
    connect(termsButton, &QPushButton::clicked,
            this, &SettingsDialog::termsRequested);

    QPushButton *privacyButton = new QPushButton(tr("隐私政策"), this);
    privacyButton->setObjectName(QStringLiteral("privacyButton"));
    privacyButton->setAccessibleName(tr("打开隐私政策"));
    privacyButton->setCursor(Qt::PointingHandCursor);
    connect(privacyButton, &QPushButton::clicked,
            this, &SettingsDialog::privacyRequested);

    QGridLayout *infoGrid = new QGridLayout();
    infoGrid->setHorizontalSpacing(ui::Spacing::S);
    infoGrid->setVerticalSpacing(ui::Spacing::S);
    infoGrid->addWidget(checkUpdateButton, 0, 0);
    infoGrid->addWidget(aboutUsButton, 0, 1);
    infoGrid->addWidget(termsButton, 1, 0);
    infoGrid->addWidget(privacyButton, 1, 1);

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
    layout->addWidget(m_monitorButton);
    layout->addWidget(hintLabel);
    layout->addWidget(shortcutHint);
    layout->addStretch(1);
    layout->addWidget(aboutLabel);
    layout->addWidget(versionLabel);
    layout->addLayout(infoGrid);
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
