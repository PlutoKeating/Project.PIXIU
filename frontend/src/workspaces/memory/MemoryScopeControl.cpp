#include "MemoryScopeControl.h"
#include <QComboBox>
#include <QDialog>
#include <QEvent>
#include <QHBoxLayout>
#include <QLabel>
#include <QLineEdit>
#include <QPushButton>
#include <QRegularExpression>
#include <QVBoxLayout>

namespace pixiu {
MemoryScopeControl::MemoryScopeControl(QComboBox *combo)
    : QWidget(combo->parentWidget()), m_combo(combo)
{
    setFocusProxy(combo);
    auto *layout = new QHBoxLayout(this);
    layout->setContentsMargins(0, 0, 0, 0);
    layout->addWidget(combo, 1);
    m_custom = new QPushButton(tr("其他范围…"), this);
    m_custom->setObjectName(combo->objectName() + QStringLiteral("Custom"));
    m_custom->setAutoDefault(false);
    m_custom->setEnabled(combo->isEnabled());
    layout->addWidget(m_custom);
    combo->installEventFilter(this);
    connect(m_custom, &QPushButton::clicked, this, &MemoryScopeControl::chooseScope);
}
bool MemoryScopeControl::eventFilter(QObject *watched, QEvent *event)
{
    if (watched == m_combo && event->type() == QEvent::EnabledChange)
        m_custom->setEnabled(m_combo->isEnabled());
    return QWidget::eventFilter(watched, event);
}
void MemoryScopeControl::chooseScope()
{
    if (!m_combo->isEnabled()) return;
    QDialog dialog(this);
    dialog.setObjectName(m_combo->objectName() + QStringLiteral("Dialog"));
    dialog.setWindowTitle(tr("选择其他记忆范围"));
    auto *layout = new QVBoxLayout(&dialog);
    auto *notice = new QLabel(tr("输入完整范围名，例如 user:work 或 shared:team。选择范围不会合并、迁移或删除数据，也不会修改 Agent 配置。选择后可能刷新只读列表；共享范围的数据可能同步至可信设备，写入和遗忘仍须单独执行。"), &dialog);
    notice->setWordWrap(true);
    layout->addWidget(notice);
    auto *input = new QLineEdit(m_combo->currentData().toString(), &dialog);
    input->setObjectName(QStringLiteral("customScopeInput"));
    input->setAccessibleName(tr("完整记忆范围"));
    layout->addWidget(input);
    auto *hint = new QLabel(tr("格式：user: 或 shared:，后接英文字母、数字、点号、下划线或连字符；总长不超过 256 字符，不接受空格或通配符。接口能力不一致时以后端明确错误为准，不会自动换范围。"), &dialog);
    hint->setWordWrap(true);
    layout->addWidget(hint);
    auto *buttons = new QHBoxLayout;
    auto *cancel = new QPushButton(tr("取消"), &dialog);
    auto *use = new QPushButton(tr("使用此范围"), &dialog);
    use->setObjectName(QStringLiteral("customScopeUse"));
    cancel->setObjectName(QStringLiteral("customScopeCancel"));
    cancel->setDefault(true);
    use->setAutoDefault(false);
    buttons->addStretch();
    buttons->addWidget(cancel);
    buttons->addWidget(use);
    layout->addLayout(buttons);
    const QRegularExpression valid(QStringLiteral("\\A(user|shared):[A-Za-z0-9._-]+\\z"));
    auto acceptable = [=]() { return input->text().size() <= 256 && valid.match(input->text()).hasMatch(); };
    auto validate = [=]() { use->setEnabled(acceptable()); };
    connect(input, &QLineEdit::textChanged, &dialog, validate);
    connect(cancel, &QPushButton::clicked, &dialog, &QDialog::reject);
    connect(use, &QPushButton::clicked, &dialog, &QDialog::accept);
    validate();
    dialog.resize(480, 250);
    if (dialog.exec() != QDialog::Accepted || !m_combo->isEnabled()
        || !acceptable()) return;
    const QString scope = input->text();
    int index = m_combo->findData(scope);
    if (index < 0) {
        m_combo->addItem(scope, scope);
        index = m_combo->count() - 1;
    }
    m_combo->setCurrentIndex(index);
}
}
