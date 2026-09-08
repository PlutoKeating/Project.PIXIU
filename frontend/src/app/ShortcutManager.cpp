#include "app/ShortcutManager.h"

#include <QCoreApplication>
#include <QKeySequence>
#include <QLoggingCategory>
#include <QShortcut>

#ifdef PIXIU_HAVE_KYSDK
#include <kysdk/desktop/libkyshortcut.h>
#include <QDBusConnection>
#include <QDBusConnectionInterface>
#include <QDBusServiceWatcher>
#include <QDBusMessage>
#include <QFileInfo>
#include <QProcess>
#include <QTimer>
#endif

Q_LOGGING_CATEGORY(lcShortcut, "pixiu.shortcut")

namespace {
#ifdef PIXIU_HAVE_KYSDK
// 系统级全局快捷键名称：全局唯一，用于创建/更新/删除。
const char kToggleShortcutName[] = "pixiu.activate";
const char kShortcutService[] = "com.kylin.kysdk.shortcut";
#endif

} // namespace

ShortcutManager::ShortcutManager(QWidget *contextWidget, QObject *parent)
    : QObject(parent)
    , m_contextWidget(contextWidget)
{
#ifdef PIXIU_HAVE_KYSDK
    m_servicePoll = new QTimer(this);
    m_servicePoll->setInterval(100);
    connect(m_servicePoll, &QTimer::timeout, this, [this]() {
        updateKylinServiceState();
        if (++m_serviceChecks >= 50) m_servicePoll->stop();
    });
    auto *watcher = new QDBusServiceWatcher(QString::fromLatin1(kShortcutService),
        QDBusConnection::sessionBus(), QDBusServiceWatcher::WatchForOwnerChange, this);
    connect(watcher, &QDBusServiceWatcher::serviceOwnerChanged, this,
        [this]() { updateKylinServiceState(); });
#endif
}

ShortcutManager::~ShortcutManager()
{
    releaseToggleShortcut();
}

bool ShortcutManager::registerToggleShortcut(const QKeySequence &sequence)
{
    releaseToggleShortcut();
    m_sequence = sequence.isEmpty()
                     ? QKeySequence(QStringLiteral("Ctrl+Alt+P"))
                     : sequence;

#ifdef PIXIU_HAVE_KYSDK
    // 优先使用 kysdk 系统级全局快捷键；失败（按键冲突、无桌面服务等）时
    // 降级到 Qt ApplicationShortcut，保证唤起功能可用。
    if (registerKylinGlobalShortcut()) {
        updateKylinServiceState();
        if (!isGlobal() && startKylinService()) {
            m_serviceChecks = 0;
            m_servicePoll->start();
        }
        return true;
    }
#endif

    return installFallback();
}

bool ShortcutManager::installFallback()
{
    if (m_shortcut) return true;
    if (!m_contextWidget) {
        qCWarning(lcShortcut) << "no context widget; shortcut not registered";
        return false;
    }

    m_shortcut = new QShortcut(m_sequence, m_contextWidget, nullptr, nullptr,
                               Qt::ApplicationShortcut);
    m_shortcut->setObjectName(QStringLiteral("toggleChatShortcut"));
    connect(m_shortcut, &QShortcut::activated, this, &ShortcutManager::toggleRequested);

    qCInfo(lcShortcut) << "registered Qt fallback shortcut"
                       << m_sequence.toString(QKeySequence::PortableText);
    return true;
}

QKeySequence ShortcutManager::currentSequence() const
{
    return m_sequence;
}

void ShortcutManager::releaseToggleShortcut()
{
#ifdef PIXIU_HAVE_KYSDK
    m_servicePoll->stop();
    const int result = m_globalRegistered ? kdk_shortcut_delete_global_shortcut(kToggleShortcutName)
                                          : KYSDK_SHORTCUT_NOT_EXISTS;
    m_globalRegistered = false;
    if (result == KYSDK_SUCCESS) {
        qCInfo(lcShortcut) << "removed Kylin global shortcut" << kToggleShortcutName;
    } else if (result != KYSDK_SHORTCUT_NOT_EXISTS && result != KYSDK_SHORTCUT_NAME_ERROR) {
        qCWarning(lcShortcut) << "failed to remove Kylin global shortcut, error code:" << result;
    }
#endif
    setGlobalAvailable(false);

    if (m_shortcut) {
        // 释放调用发生在退出路径，不存在快捷键事件处理中的再入删除，
        // 直接删除以保证 QShortcutMap 立即注销。
        delete m_shortcut;
        m_shortcut = nullptr;
    }
}

#ifdef PIXIU_HAVE_KYSDK
bool ShortcutManager::kylinServiceReady() const
{
    auto *bus = QDBusConnection::sessionBus().interface();
    return bus && bus->isServiceRegistered(QString::fromLatin1(kShortcutService)).value();
}

bool ShortcutManager::startKylinService()
{
    // Official SDK autostart entry. The shared desktop service outlives PIXIU;
    // do not parent it to the app or terminate it when the window closes.
    const QString program = QStringLiteral("/usr/bin/kdkshortcut");
    const bool started = QFileInfo(program).isExecutable() && QProcess::startDetached(program, {});
    if (!started) qCWarning(lcShortcut) << "Kylin shortcut service unavailable; using application shortcut";
    return started;
}

void ShortcutManager::updateKylinServiceState()
{
    if (!m_globalRegistered) return;
    const bool ready = kylinServiceReady();
    if (ready) {
        m_servicePoll->stop();
        delete m_shortcut;
        m_shortcut = nullptr;
    } else {
        installFallback();
    }
    setGlobalAvailable(ready);
}

bool ShortcutManager::clearStaleKylinRegistration()
{
    // V11 can retain compositor registrations after the SDK helper exits, even
    // when its settings entry has been deleted. Only unregister PIXIU's names
    // in the SDK component; never cleanUp the component or steal another key.
    bool removed = false;
    for (const QString &name : {QString::fromLatin1(kToggleShortcutName),
                               QStringLiteral("pixiu-frontend.toggle-chat")}) {
        auto request = QDBusMessage::createMethodCall(QStringLiteral("org.kde.kglobalaccel"),
            QStringLiteral("/kglobalaccel"), QStringLiteral("org.kde.KGlobalAccel"),
            QStringLiteral("unregister"));
        request << QStringLiteral("kysdk-keybindings") << name;
        const auto reply = QDBusConnection::sessionBus().call(request, QDBus::Block, 250);
        if (reply.type() == QDBusMessage::ReplyMessage && reply.arguments().size() == 1
            && reply.arguments().first().toBool()) removed = true;
    }
    return removed;
}

bool ShortcutManager::registerKylinGlobalShortcut()
{
    // Upgrade migration: this name belonged exclusively to the removed desktop
    // executable. Never enumerate or delete other applications' bindings.
    const int legacyResult = kdk_shortcut_delete_global_shortcut("pixiu-frontend.toggle-chat");
    if (legacyResult != KYSDK_SUCCESS && legacyResult != KYSDK_SHORTCUT_NOT_EXISTS
        && legacyResult != KYSDK_SHORTCUT_NAME_ERROR) {
        qCWarning(lcShortcut) << "failed to remove retired PIXIU shortcut, error code:" << legacyResult;
    }
    const QByteArray name(kToggleShortcutName);
    const QByteArray key =
        m_sequence.toString(QKeySequence::PortableText).toUtf8();
    const QByteArray action = QCoreApplication::applicationFilePath().toUtf8();

    int result = kdk_shortcut_create_global_shortcut(name.constData(),
                                                     key.constData(),
                                                     action.constData());
    if (result == KYSDK_SUCCESS) {
        m_globalRegistered = true;
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
            m_globalRegistered = true;
            qCInfo(lcShortcut) << "updated existing Kylin global shortcut" << key.constData();
            return true;
        }
    }

    if (result == KYSDK_SHORTCUT_EXISTED && clearStaleKylinRegistration()) {
        result = kdk_shortcut_create_global_shortcut(name.constData(), key.constData(), action.constData());
        if (result == KYSDK_SHORTCUT_EXISTED)
            result = kdk_shortcut_set_global_shortcut(name.constData(), key.constData(), action.constData());
        if (result == KYSDK_SUCCESS) {
            m_globalRegistered = true;
            qCInfo(lcShortcut) << "recovered stale PIXIU shortcut registration";
            return true;
        }
    }
    qCWarning(lcShortcut) << "failed to register Kylin global shortcut" << key.constData()
                          << "error code:" << result;
    return false;
}
#endif

void ShortcutManager::setGlobalAvailable(bool available)
{
    if (m_globalAvailable == available) return;
    m_globalAvailable = available;
    emit availabilityChanged(available);
}
