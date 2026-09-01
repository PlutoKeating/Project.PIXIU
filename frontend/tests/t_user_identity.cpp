#include <QTest>

#include <pwd.h>

#include "app/UserIdentity.h"

// displayUserName 三路径单测：GECOS 全名 / GECOS 空回退 $USER / 双空兜底。
// 通过注入 ui::PasswdReader 构造假条目，确定性验证，不依赖机器账户状态。
class TestUserIdentity : public QObject
{
    Q_OBJECT

private slots:
    void gecosFullNameWins();
    void gecosTakesFirstCommaSegment();
    void gecosEmptyFallsBackToUserEnv();
    void noEntryAndNoUserFallsBackToChineseFallback();
};

namespace {

struct passwd s_full{};
struct passwd s_empty{};

// 返回一个 pw_gecos = "PlutoKeating,Office,555" 的假条目。
struct passwd *fullReader(uid_t)
{
    static char gecos[] = "PlutoKeating,Office,555";
    s_full.pw_gecos = gecos;
    return &s_full;
}

// 返回 pw_gecos = "  Pluto Keating, Office" 的假条目（带前后空白，验证首段 trim）。
struct passwd *trimmedReader(uid_t)
{
    static char gecos[] = "  Pluto Keating, Office";
    s_full.pw_gecos = gecos;
    return &s_full;
}

// 返回 pw_gecos 为空的假条目（GECOS 空 → 回退 $USER）。
struct passwd *emptyReader(uid_t)
{
    static char gecos[] = "";
    s_empty.pw_gecos = gecos;
    return &s_empty;
}

// 返回 NULL（无 passwd 条目 → 回退 $USER；$USER 也空 → 兜底）。
struct passwd *nullReader(uid_t)
{
    return nullptr;
}

} // namespace

void TestUserIdentity::gecosFullNameWins()
{
    QCOMPARE(ui::displayUserName(0, fullReader), QStringLiteral("PlutoKeating"));
}

void TestUserIdentity::gecosTakesFirstCommaSegment()
{
    // 逗号分隔取首段并 trim：与机器无关，确定性验证“首段为姓名”。
    QCOMPARE(ui::displayUserName(0, trimmedReader),
             QStringLiteral("Pluto Keating"));
}

void TestUserIdentity::gecosEmptyFallsBackToUserEnv()
{
    qputenv("USER", "pluto");
    const QString name = ui::displayUserName(0, emptyReader);
    qunsetenv("USER");
    QCOMPARE(name, QStringLiteral("pluto"));
}

void TestUserIdentity::noEntryAndNoUserFallsBackToChineseFallback()
{
    qunsetenv("USER");
    QCOMPARE(ui::displayUserName(0, nullReader), QStringLiteral("用户"));
}

QTEST_APPLESS_MAIN(TestUserIdentity)
#include "t_user_identity.moc"
