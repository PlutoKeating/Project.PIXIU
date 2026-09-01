#include <QTest>

#include <QByteArray>
#include <QDateTime>
#include <QDir>
#include <QFile>

#include "app/UpgradeUtils.h"

// 版本比较 + sha256 校验 + GitHub release 解析的纯函数单测（无 UI / 无网络）。
// 依赖 QtTest（QTEST_APPLESS_MAIN，offscreen 无需 GUI）。
class TestUpgradeUtils : public QObject
{
    Q_OBJECT

private slots:
    void compareEqual();
    void compareGreater();
    void compareLess();
    void comparePrefixLongerIsGreater();
    void comparePrefixSameWithZeroSegment();
    void compareFewerSegmentsZeroPad();
    void normalizeStripsV();
    void normalizeWithoutV();
    void sha256KnownVector();
    void verifyCorrect();
    void verifyWrong();
    void verifyMissingFile();
    void verifyRejectsMismatchedFilename();
    void debianArchitectureMapsKnownNames();
    void parseReleaseValid();
    void parseReleaseSelectsRequestedArchitecture();
    void parseReleaseRejectsMismatchedAssetPair();
    void parseReleaseMissingDeb();
    void parseReleaseMissingSha();
    void parseReleaseInvalidJson();
};

namespace {

// 写一个临时文件并返回路径（调用方负责 remove）。
QString writeTempFile(const QByteArray &content)
{
    static int counter = 0;
    const QString path = QDir::tempPath()
        + QStringLiteral("/pixiu_upgrade_utils_%1.bin").arg(++counter);
    QFile file(path);
    if (!file.open(QIODevice::WriteOnly)) {
        return QString();
    }
    file.write(content);
    file.close();
    return path;
}

} // namespace

void TestUpgradeUtils::compareEqual()
{
    QCOMPARE(ui::compareVersions(QStringLiteral("1.2.3"), QStringLiteral("1.2.3")),
             0);
}

void TestUpgradeUtils::compareGreater()
{
    QCOMPARE(ui::compareVersions(QStringLiteral("1.2.4"), QStringLiteral("1.2.3")),
             1);
}

void TestUpgradeUtils::compareLess()
{
    QCOMPARE(ui::compareVersions(QStringLiteral("1.2.2"), QStringLiteral("1.2.3")),
             -1);
}

void TestUpgradeUtils::comparePrefixLongerIsGreater()
{
    // 前缀不等长：0.1.6.1 > 0.1.6（第 4 段 1 > 补 0）；对称方向 -1。
    QCOMPARE(ui::compareVersions(QStringLiteral("0.1.6.1"), QStringLiteral("0.1.6")),
             1);
    QCOMPARE(ui::compareVersions(QStringLiteral("0.1.6"), QStringLiteral("0.1.6.1")),
             -1);
}

void TestUpgradeUtils::comparePrefixSameWithZeroSegment()
{
    // 缺段视为 0：0.1.6 == 0.1.6.0。
    QCOMPARE(ui::compareVersions(QStringLiteral("0.1.6"), QStringLiteral("0.1.6.0")),
             0);
}

void TestUpgradeUtils::compareFewerSegmentsZeroPad()
{
    // 段数更少补齐 0：1.2 == 1.2.0。
    QCOMPARE(ui::compareVersions(QStringLiteral("1.2"), QStringLiteral("1.2.0")),
             0);
}

void TestUpgradeUtils::normalizeStripsV()
{
    QCOMPARE(ui::normalizeVersion(QStringLiteral("v0.1.6")),
             QStringLiteral("0.1.6"));
}

void TestUpgradeUtils::normalizeWithoutV()
{
    QCOMPARE(ui::normalizeVersion(QStringLiteral("0.1.6")),
             QStringLiteral("0.1.6"));
}

void TestUpgradeUtils::sha256KnownVector()
{
    // 标准向量 "abc" 的 SHA-256。
    const QByteArray expected = QByteArrayLiteral(
        "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad");
    QCOMPARE(ui::sha256Hex(QByteArrayLiteral("abc")), expected);
}

void TestUpgradeUtils::verifyCorrect()
{
    const QByteArray content = QByteArrayLiteral("pixiu-package-data");
    const QString path = writeTempFile(content);
    QVERIFY(!path.isEmpty());
    const QString hex = QString::fromLatin1(ui::sha256Hex(content));
    QVERIFY(ui::verifySha256(path, hex));
    QFile::remove(path);
}

void TestUpgradeUtils::verifyWrong()
{
    const QByteArray content = QByteArrayLiteral("pixiu-package-data");
    const QString path = writeTempFile(content);
    QVERIFY(!path.isEmpty());
    // 与真实哈希不符的全 0 摘要 → false。
    const QString bogus = QStringLiteral(
        "0000000000000000000000000000000000000000000000000000000000000000");
    QVERIFY(!ui::verifySha256(path, bogus));
    QFile::remove(path);
}

void TestUpgradeUtils::verifyMissingFile()
{
    const QString path = QDir::tempPath()
        + QStringLiteral("/pixiu_missing_%1.bin")
              .arg(QDateTime::currentMSecsSinceEpoch());
    QVERIFY(!ui::verifySha256(path, QStringLiteral(
        "0000000000000000000000000000000000000000000000000000000000000000")));
}

void TestUpgradeUtils::verifyRejectsMismatchedFilename()
{
    const QByteArray content = QByteArrayLiteral("pixiu-package-data");
    const QString path = writeTempFile(content);
    QVERIFY(!path.isEmpty());
    const QString manifest =
        QString::fromLatin1(ui::sha256Hex(content))
        + QStringLiteral("  another-package.deb\n");
    QVERIFY(!ui::verifySha256(
        path, manifest, QStringLiteral("pixiu_0.1.6-1_amd64.deb")));
    QFile::remove(path);
}

void TestUpgradeUtils::debianArchitectureMapsKnownNames()
{
    const QString architecture = ui::debianArchitecture();
    QVERIFY(!architecture.isEmpty());
    QVERIFY(architecture != QStringLiteral("x86_64"));
    QVERIFY(architecture != QStringLiteral("aarch64"));
}

void TestUpgradeUtils::parseReleaseValid()
{
    const QByteArray json = QByteArray(R"(
        {
            "tag_name": "v0.1.6",
            "assets": [
                {"name": "pixiu_0.1.6-1_amd64.deb",
                 "browser_download_url": "https://github.com/PlutoKeating/Project.PIXIU/releases/download/v0.1.6/pixiu_0.1.6-1_amd64.deb"},
                {"name": "pixiu_0.1.6-1_amd64.deb.sha256",
                 "browser_download_url": "https://github.com/PlutoKeating/Project.PIXIU/releases/download/v0.1.6/pixiu_0.1.6-1_amd64.deb.sha256"}
            ]
        }
    )");
    ui::ReleaseInfo info;
    QVERIFY(ui::parseRelease(json, info, QStringLiteral("amd64")));
    QCOMPARE(info.tag, QStringLiteral("0.1.6"));
    QCOMPARE(info.architecture, QStringLiteral("amd64"));
    QCOMPARE(info.debName, QStringLiteral("pixiu_0.1.6-1_amd64.deb"));
    QCOMPARE(info.debUrl,
             QStringLiteral("https://github.com/PlutoKeating/Project.PIXIU/releases/download/v0.1.6/pixiu_0.1.6-1_amd64.deb"));
    QCOMPARE(info.shaUrl,
             QStringLiteral("https://github.com/PlutoKeating/Project.PIXIU/releases/download/v0.1.6/pixiu_0.1.6-1_amd64.deb.sha256"));
}

void TestUpgradeUtils::parseReleaseSelectsRequestedArchitecture()
{
    const QByteArray json = QByteArray(R"({
        "tag_name": "v0.1.6",
        "assets": [
            {"name":"pixiu_0.1.6-1_amd64.deb",
             "browser_download_url":"https://github.com/a/amd64.deb"},
            {"name":"pixiu_0.1.6-1_amd64.deb.sha256",
             "browser_download_url":"https://github.com/a/amd64.deb.sha256"},
            {"name":"pixiu_0.1.6-1_arm64.deb",
             "browser_download_url":"https://github.com/a/arm64.deb"},
            {"name":"pixiu_0.1.6-1_arm64.deb.sha256",
             "browser_download_url":"https://github.com/a/arm64.deb.sha256"}
        ]
    })");
    ui::ReleaseInfo info;
    QVERIFY(ui::parseRelease(json, info, QStringLiteral("arm64")));
    QCOMPARE(info.debName, QStringLiteral("pixiu_0.1.6-1_arm64.deb"));
    QCOMPARE(info.debUrl, QStringLiteral("https://github.com/a/arm64.deb"));
}

void TestUpgradeUtils::parseReleaseRejectsMismatchedAssetPair()
{
    const QByteArray json = QByteArray(R"({
        "tag_name": "v0.1.6",
        "assets": [
            {"name":"pixiu_0.1.5-1_amd64.deb",
             "browser_download_url":"https://github.com/a/old.deb"},
            {"name":"pixiu_0.1.6-1_arm64.deb.sha256",
             "browser_download_url":"https://github.com/a/wrong.sha256"}
        ]
    })");
    ui::ReleaseInfo info;
    QVERIFY(!ui::parseRelease(json, info, QStringLiteral("amd64")));
}

void TestUpgradeUtils::parseReleaseMissingDeb()
{
    // 只有 .sha256 asset，缺 deb → false。
    const QByteArray json = QByteArray(R"(
        {
            "tag_name": "v0.1.6",
            "assets": [
                {"name": "pixiu_0.1.6-1_amd64.deb.sha256",
                 "browser_download_url": "https://github.com/PlutoKeating/Project.PIXIU/releases/download/v0.1.6/pixiu_0.1.6-1_amd64.deb.sha256"}
            ]
        }
    )");
    ui::ReleaseInfo info;
    QVERIFY(!ui::parseRelease(json, info, QStringLiteral("amd64")));
}

void TestUpgradeUtils::parseReleaseMissingSha()
{
    // 只有 deb asset，缺 .sha256 → false。
    const QByteArray json = QByteArray(R"(
        {
            "tag_name": "v0.1.6",
            "assets": [
                {"name": "pixiu_0.1.6-1_amd64.deb",
                 "browser_download_url": "https://github.com/PlutoKeating/Project.PIXIU/releases/download/v0.1.6/pixiu_0.1.6-1_amd64.deb"}
            ]
        }
    )");
    ui::ReleaseInfo info;
    QVERIFY(!ui::parseRelease(json, info, QStringLiteral("amd64")));
}

void TestUpgradeUtils::parseReleaseInvalidJson()
{
    ui::ReleaseInfo info;
    QVERIFY(!ui::parseRelease(
        QByteArrayLiteral("not a json {"), info, QStringLiteral("amd64")));
}

QTEST_APPLESS_MAIN(TestUpgradeUtils)
#include "t_upgrade_utils.moc"
