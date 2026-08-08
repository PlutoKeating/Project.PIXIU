#include "app/ShortcutManager.h"

#include <QCoreApplication>
#include <QKeySequence>
#include <QLoggingCategory>
#include <QShortcut>

#ifdef PIXIU_HAVE_KYSDK
#include <kysdk/desktop/libkyshortcut.h>
#endif

Q_LOGGING_CATEGORY(lcShortcut, "pixiu.shortcut")

namespace {

const QString kToggleKeySequence = QStringLiteral("Ctrl+Alt+P");

#ifdef PIXIU_HAVE_KYSDK
// 系统级全局快捷键名称：全局唯一，用于创建/更新/删除。
const char kToggleShortcutName[] = "pixiu-frontend.toggle-chat";
#endif

} // namespace

ShortcutManager::ShortcutManager(QWidget *contextWidget, QObject *parent)
    : QObject(parent)
    , m_contextWidget(contextWidget)
{
}

ShortcutManager::~ShortcutManager()
{
    releaseToggleShortcut();
}

bool ShortcutManager::registerToggleShortcut()
{
#ifdef PIXIU_HAVE_KYSDK
    // 优先使用 kysdk 系统级全局快捷键；失败（按键冲突、无桌面服务等）时
    // 降级到 Qt ApplicationShortcut，保证唤起功能可用。
    if (registerKylinGlobalShortcut()) {
        return true;
    }
#endif

    if (!m_contextWidget) {
        qCWarning(lcShortcut) << "no context widget; shortcut not registered";
        return false;
    }

    m_shortcut = new QShortcut(QKeySequence(kToggleKeySequence),
                               m_contextWidget, nullptr, nullptr,
                               Qt::ApplicationShortcut);
    m_shortcut->setObjectName(QStringLiteral("toggleChatShortcut"));
    connect(m_shortcut, &QShortcut::activated, this, &ShortcutManager::toggleRequested);

    qCInfo(lcShortcut) << "registered Qt fallback shortcut" << kToggleKeySequence;
    return true;
}

void ShortcutManager::releaseToggleShortcut()
{
#ifdef PIXIU_HAVE_KYSDK
    const int result = kdk_shortcut_delete_global_shortcut(kToggleShortcutName);
    if (result == KYSDK_SUCCESS) {
        qCInfo(lcShortcut) << "removed Kylin global shortcut" << kToggleShortcutName;
    } else if (result != KYSDK_SHORTCUT_NOT_EXISTS && result != KYSDK_SHORTCUT_NAME_ERROR) {
        qCWarning(lcShortcut) << "failed to remove Kylin global shortcut, error code:" << result;
    }
#endif

    if (m_shortcut) {
        // 释放调用发生在退出路径，不存在快捷键事件处理中的再入删除，
        // 直接删除以保证 QShortcutMap 立即注销。
        delete m_shortcut;
        m_shortcut = nullptr;
    }
}

#ifdef PIXIU_HAVE_KYSDK
bool ShortcutManager::registerKylinGlobalShortcut()
{
    const QByteArray name(kToggleShortcutName);
    const QByteArray key =
        QKeySequence(kToggleKeySequence).toString(QKeySequence::PortableText).toUtf8();
    const QByteArray action = QCoreApplication::applicationFilePath().toUtf8();

    int result = kdk_shortcut_create_global_shortcut(name.constData(),
                                                     key.constData(),
                                                     action.constData());
    if (result == KYSDK_SUCCESS) {
        qCInfo(lcShortcut) << "registered Kylin global shortcut" << key.constData()
                           << "->" << action.constData();
        return true;
    }

    // 名称已存在（上次异常退出残留或重复注册）：更新按键与动作。
    if (result == KYSDK_SHORTCUT_EXISTED) {
        result = kdk_shortcut_set_global_shortcut(name.constData(),
                                                  key.constData(),
                                                  action.constData());
        if (result == KYSDK_SUCCESS) {
            qCInfo(lcShortcut) << "updated existing Kylin global shortcut" << key.constData();
            return true;
        }
    }

    qCWarning(lcShortcut) << "failed to register Kylin global shortcut" << key.constData()
                          << "error code:" << result;
    return false;
}
#endif
