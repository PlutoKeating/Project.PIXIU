#include "app/UserIdentity.h"

#include <QByteArray>
#include <QString>
#include <QtGlobal>

#include <cstring>
#include <pwd.h>
#include <unistd.h>

namespace ui {

namespace {

// 取 GECOS 字段逗号分隔首段作为账户全名。
// GECOS 约定第 1 项为真实姓名，其后为办公室/电话等附加信息（逗号分隔），
// 因此取首段；首段可能含前后空白（如 " Pluto"），统一 trim。
QString gecosFullName(const char *gecos)
{
    if (gecos == nullptr || *gecos == '\0') {
        return QString();
    }
    const char *comma = std::strchr(gecos, ',');
    const QByteArray first =
        comma ? QByteArray(gecos, comma - gecos) : QByteArray(gecos);
    return QString::fromUtf8(first).trimmed();
}

} // namespace

QString displayUserName(uid_t uid, PasswdReader reader)
{
    // 1. 优先取账户全名（passwd GECOS 逗号分隔首段）。
    if (reader != nullptr) {
        if (const struct passwd *entry = reader(uid)) {
            const QString fullName = gecosFullName(entry->pw_gecos);
            if (!fullName.isEmpty()) {
                return fullName;
            }
        }
    }

    // 2. GECOS 为空（或条目缺失）→ 回退 login username（$USER）。
    const QString user = qEnvironmentVariable("USER");
    if (!user.isEmpty()) {
        return user;
    }

    // 3. 再空 → 中文安全兜底。
    return QStringLiteral("用户");
}

} // namespace ui
