#include "app/ShortcutManager.h"

#include <QKeySequence>
#include <QLoggingCategory>
#include <QShortcut>

Q_LOGGING_CATEGORY(lcShortcut, "pixiu.shortcut")

ShortcutManager::ShortcutManager(QWidget *contextWidget, QObject *parent)
    : QObject(parent)
    , m_contextWidget(contextWidget)
{
}

bool ShortcutManager::registerToggleShortcut()
{
    if (!m_contextWidget) {
        qCWarning(lcShortcut) << "no context widget; shortcut not registered";
        return false;
    }

    m_shortcut = new QShortcut(QKeySequence(QStringLiteral("Ctrl+Alt+P")),
                               m_contextWidget, nullptr, nullptr,
                               Qt::ApplicationShortcut);
    m_shortcut->setObjectName(QStringLiteral("toggleChatShortcut"));
    connect(m_shortcut, &QShortcut::activated, this, &ShortcutManager::toggleRequested);

    qCInfo(lcShortcut) << "registered dev shortcut Ctrl+Alt+P (Kylin global shortcut in Phase 7)";
    return true;
}
