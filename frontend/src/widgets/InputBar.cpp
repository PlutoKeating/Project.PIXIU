#include "widgets/InputBar.h"

#include <QApplication>
#include <QHBoxLayout>
#include <QKeyEvent>
#include <QLabel>
#include <QMenu>
#include <QPlainTextEdit>
#include <QPushButton>
#include <QVBoxLayout>

#include "app/UiIcons.h"
#include "app/UiTokens.h"

InputBar::InputBar(QWidget *parent)
    : QWidget(parent)
{
    setObjectName(QStringLiteral("inputBar"));
    const QColor iconColor = QApplication::palette().color(QPalette::Text);

    // ── 输入区上方 chip 快捷行（真实能力入口，图标 + 短文字）────────────
    const auto makeChip = [this, iconColor](const QString &text,
                                            const QIcon &icon,
                                            const QString &objectName,
                                            const QString &toolTip) {
        QPushButton *chip = new QPushButton(icon, text, this);
        chip->setObjectName(objectName);
        chip->setProperty("chipRole", QStringLiteral("chip"));
        chip->setAccessibleName(text);
        chip->setToolTip(toolTip);
        chip->setCursor(Qt::PointingHandCursor);
        chip->setIconSize(QSize(13, 13));
        return chip;
    };

    m_memoryChip = makeChip(tr("记忆"), ui::memoryIcon(iconColor),
                            QStringLiteral("memoryChip"),
                            tr("打开记忆面板"));
    m_settingsChip = makeChip(tr("设置"), ui::gearIcon(iconColor),
                              QStringLiteral("settingsChip"),
                              tr("打开设置"));
    m_importChip = makeChip(tr("录入"), ui::importIcon(iconColor),
                            QStringLiteral("importChip"),
                            tr("录入知识"));
    m_syncChip = makeChip(tr("同步"), ui::syncIcon(iconColor),
                          QStringLiteral("syncChip"),
                          tr("打开同步面板"));
    m_moreChip = makeChip(tr("更多"), ui::moreIcon(iconColor),
                          QStringLiteral("moreChip"),
                          tr("更多"));
    m_chips = {m_memoryChip, m_settingsChip, m_importChip, m_syncChip};

    connect(m_memoryChip, &QPushButton::clicked,
            this, &InputBar::memoryPanelRequested);
    connect(m_settingsChip, &QPushButton::clicked,
            this, &InputBar::settingsRequested);
    connect(m_importChip, &QPushButton::clicked,
            this, &InputBar::attachRequested);
    connect(m_syncChip, &QPushButton::clicked,
            this, &InputBar::syncPanelRequested);
    connect(m_moreChip, &QPushButton::clicked,
            this, &InputBar::showMoreMenu);
    m_moreMenu = new QMenu(this);
    m_moreMenu->setObjectName(QStringLiteral("moreMenu"));
    QAction *memoryAction = m_moreMenu->addAction(tr("记忆面板"));
    QAction *settingsAction = m_moreMenu->addAction(tr("设置"));
    QAction *importAction = m_moreMenu->addAction(tr("录入知识"));
    QAction *syncAction = m_moreMenu->addAction(tr("同步面板"));
    connect(memoryAction, &QAction::triggered,
            this, &InputBar::memoryPanelRequested);
    connect(settingsAction, &QAction::triggered,
            this, &InputBar::settingsRequested);
    connect(importAction, &QAction::triggered,
            this, &InputBar::attachRequested);
    connect(syncAction, &QAction::triggered,
            this, &InputBar::syncPanelRequested);

    QHBoxLayout *chipsRow = new QHBoxLayout();
    chipsRow->setContentsMargins(0, 0, 0, 0);
    chipsRow->setSpacing(ui::Spacing::XS);
    for (QPushButton *chip : m_chips) {
        chipsRow->addWidget(chip);
    }
    chipsRow->addWidget(m_moreChip);
    chipsRow->addStretch(1);

    // ── 圆角输入卡片：多行输入 + 状态 badge + 发送按钮 ──────────────────
    QWidget *card = new QWidget(this);
    card->setObjectName(QStringLiteral("inputCard"));
    // 纯 QWidget 子类需显式启用样式背景，QSS 中的圆角卡片底色才会绘制。
    card->setAttribute(Qt::WA_StyledBackground, true);

    m_attachButton = new QPushButton(tr("📎"), card);
    m_attachButton->setObjectName(QStringLiteral("attachButton"));
    m_attachButton->setAccessibleName(tr("录入图片或文件"));
    m_attachButton->setFlat(true);
    // 录入对话框已实现（图片拖入预览 + MANUAL_CONFIG 载荷），文案不再标注“后续”。
    m_attachButton->setToolTip(tr("录入图片/文件"));
    m_attachButton->setCursor(Qt::PointingHandCursor);
    connect(m_attachButton, &QPushButton::clicked, this, &InputBar::attachRequested);

    m_editor = new QPlainTextEdit(card);
    m_editor->setObjectName(QStringLiteral("inputEdit"));
    m_editor->setAccessibleName(tr("问题输入框"));
    m_editor->setPlaceholderText(tr("输入问题，或拖入图片录入…"));
    m_editor->setVerticalScrollBarPolicy(Qt::ScrollBarAsNeeded);
    m_editor->setHorizontalScrollBarPolicy(Qt::ScrollBarAlwaysOff);
    m_editor->setTabChangesFocus(false);
    m_editor->setMinimumHeight(44);
    m_editor->setMaximumHeight(72);
    m_editor->installEventFilter(this);
    connect(m_editor, &QPlainTextEdit::textChanged,
            this, &InputBar::updateSendEnabled);

    m_sendButton = new QPushButton(tr("发送"), card);
    m_sendButton->setObjectName(QStringLiteral("sendButton"));
    m_sendButton->setAccessibleName(tr("发送"));
    m_sendButton->setCursor(Qt::PointingHandCursor);
    m_sendButton->setEnabled(false);
    m_sendButton->setStyleSheet(ui::accentButtonStyle());
    connect(m_sendButton, &QPushButton::clicked, this, &InputBar::onSendClicked);

    m_stateBadge = new QLabel(tr("● 离线"), card);
    m_stateBadge->setObjectName(QStringLiteral("inputStateBadge"));
    m_stateBadge->setAccessibleName(tr("后端连接状态"));
    m_stateBadge->setStyleSheet(ui::textStyle(ui::Role::Muted));

    QHBoxLayout *editorRow = new QHBoxLayout();
    editorRow->setContentsMargins(0, 0, 0, 0);
    editorRow->setSpacing(ui::Spacing::XS);
    editorRow->addWidget(m_attachButton);
    editorRow->addWidget(m_editor, 1);

    QHBoxLayout *bottomRow = new QHBoxLayout();
    bottomRow->setContentsMargins(0, 0, 0, 0);
    bottomRow->setSpacing(ui::Spacing::S);
    bottomRow->addWidget(m_stateBadge);
    bottomRow->addStretch(1);
    bottomRow->addWidget(m_sendButton);

    QVBoxLayout *cardLayout = new QVBoxLayout(card);
    cardLayout->setContentsMargins(ui::Spacing::S, ui::Spacing::S,
                                   ui::Spacing::S, ui::Spacing::S);
    cardLayout->setSpacing(ui::Spacing::XS);
    cardLayout->addLayout(editorRow);
    cardLayout->addLayout(bottomRow);

    QVBoxLayout *root = new QVBoxLayout(this);
    root->setContentsMargins(0, 0, 0, 0);
    root->setSpacing(ui::Spacing::XS);
    root->addLayout(chipsRow);
    root->addWidget(card);

    // 明暗主题切换时重建图标颜色（ThemeService 应用 Palette 后触发）。
    connect(qApp, &QApplication::paletteChanged, this,
            [this](const QPalette &) {
                rebuildChipIcons();
                if (m_sendButton) {
                    m_sendButton->setStyleSheet(ui::accentButtonStyle());
                }
                if (m_stateBadge) {
                    m_stateBadge->setStyleSheet(ui::textStyle(
                        m_state == ConnectionState::Connected
                            ? ui::Role::Success
                            : m_state == ConnectionState::Connecting
                                ? ui::Role::Warning
                                : m_state == ConnectionState::Error
                                    ? ui::Role::Error
                                    : ui::Role::Muted));
                }
            });

    setBackendState(ConnectionState::Disconnected);
}

void InputBar::focusInput()
{
    m_editor->setFocus(Qt::ShortcutFocusReason);
}

void InputBar::clearInput()
{
    m_editor->clear();
}

void InputBar::setInputText(const QString &text)
{
    m_editor->setPlainText(text);
    m_editor->moveCursor(QTextCursor::End);
    m_editor->setFocus(Qt::OtherFocusReason);
}

void InputBar::setBackendState(ConnectionState state)
{
    m_state = state;
    const bool online = state == ConnectionState::Connected;
    QString text;
    ui::Role role = ui::Role::Muted;
    switch (state) {
    case ConnectionState::Connected:
        text = tr("● 在线");
        role = ui::Role::Success;
        break;
    case ConnectionState::Connecting:
        text = tr("● 连接中…");
        role = ui::Role::Warning;
        break;
    case ConnectionState::Error:
        text = tr("● 服务异常");
        role = ui::Role::Error;
        break;
    case ConnectionState::Disconnected:
    default:
        text = tr("● 离线");
        role = ui::Role::Muted;
        break;
    }
    m_stateBadge->setText(text);
    m_stateBadge->setStyleSheet(ui::textStyle(role));
    m_stateBadge->setVisible(true);

    // 离线/异常：禁用输入与录入入口；记忆/设置/更多入口保持可用。
    m_editor->setEnabled(online);
    m_attachButton->setEnabled(online);
    m_importChip->setEnabled(online);
    updateSendEnabled();
}

bool InputBar::eventFilter(QObject *watched, QEvent *event)
{
    if (watched == m_editor && event->type() == QEvent::KeyPress) {
        QKeyEvent *key = static_cast<QKeyEvent *>(event);
        const bool isEnter = key->key() == Qt::Key_Return
                             || key->key() == Qt::Key_Enter;
        if (isEnter && !(key->modifiers() & Qt::ShiftModifier)) {
            // Enter 发送（原 QLineEdit 语义不回归）；Shift+Enter 走默认换行。
            onSendClicked();
            return true;
        }
    }
    return QWidget::eventFilter(watched, event);
}

void InputBar::resizeEvent(QResizeEvent *event)
{
    QWidget::resizeEvent(event);
    updateChipVisibility();
}

void InputBar::onSendClicked()
{
    const QString text = m_editor->toPlainText().trimmed();
    if (text.isEmpty()) {
        return;
    }
    emit sendRequested(text);
    clearInput();
}

void InputBar::updateSendEnabled()
{
    const bool online = m_state == ConnectionState::Connected;
    m_sendButton->setEnabled(online && !m_editor->toPlainText().trimmed().isEmpty());
}

void InputBar::rebuildChipIcons()
{
    const QColor color = QApplication::palette().color(QPalette::Text);
    if (m_memoryChip) m_memoryChip->setIcon(ui::memoryIcon(color));
    if (m_settingsChip) m_settingsChip->setIcon(ui::gearIcon(color));
    if (m_importChip) m_importChip->setIcon(ui::importIcon(color));
    if (m_syncChip) m_syncChip->setIcon(ui::syncIcon(color));
    if (m_moreChip) m_moreChip->setIcon(ui::moreIcon(color));
}

void InputBar::updateChipVisibility()
{
    if (m_chips.isEmpty() || !m_moreChip) {
        return;
    }
    // 先全部显示，再从右向左隐藏直到放得下；“更多”常驻（溢出入口）。
    const int spacing = ui::Spacing::XS;
    int used = m_moreChip->sizeHint().width() + spacing * 2;
    for (QPushButton *chip : m_chips) {
        chip->setVisible(true);
        used += chip->sizeHint().width() + spacing;
    }
    const int available = width() - spacing * 2;
    for (int i = m_chips.size() - 1; i >= 0 && used > available; --i) {
        if (m_chips[i]->isVisible()) {
            m_chips[i]->setVisible(false);
            used -= m_chips[i]->sizeHint().width() + spacing;
        }
    }
}

void InputBar::showMoreMenu()
{
    if (m_moreMenu) {
        m_moreMenu->popup(m_moreChip->mapToGlobal(
            QPoint(0, m_moreChip->height())));
    }
}
