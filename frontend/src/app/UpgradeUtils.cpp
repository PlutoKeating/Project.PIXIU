#include "app/UpgradeUtils.h"

#include <QCryptographicHash>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonParseError>
#include <QRegularExpression>
#include <QStringList>
#include <QSysInfo>
#include <QtGlobal>

namespace ui {

QString normalizeVersion(const QString &tag)
{
    QString t = tag.trimmed();
    if (!t.isEmpty() && t.at(0) == QLatin1Char('v')) {
        t = t.mid(1);
    }
    return t;
}

int compareVersions(const QString &a, const QString &b)
{
    // 逐段按数字比较，缺段补 0；非数字段 toInt() 返回 0（防御）。
    const QStringList pa = normalizeVersion(a).split(QLatin1Char('.'));
    const QStringList pb = normalizeVersion(b).split(QLatin1Char('.'));
    const int n = qMax(pa.size(), pb.size());
    for (int i = 0; i < n; ++i) {
        const int va = (i < pa.size()) ? pa.at(i).toInt() : 0;
        const int vb = (i < pb.size()) ? pb.at(i).toInt() : 0;
        if (va < vb) {
            return -1;
        }
        if (va > vb) {
            return 1;
        }
    }
    return 0;
}

QByteArray sha256Hex(const QByteArray &data)
{
    return QCryptographicHash::hash(data, QCryptographicHash::Sha256).toHex();
}

QString sha256FromManifest(const QString &manifest,
                           const QString &expectedFileName)
{
    const QStringList tokens = manifest.trimmed().split(
        QRegularExpression(QStringLiteral("\\s+")), Qt::SkipEmptyParts);
    if (tokens.isEmpty() || tokens.size() > 2
        || !QRegularExpression(QStringLiteral("^[0-9A-Fa-f]{64}$"))
                .match(tokens.first())
                .hasMatch()) {
        return QString();
    }
    if (!expectedFileName.isEmpty()
        && (tokens.size() != 2
            || QFileInfo(tokens.last()).fileName() != expectedFileName)) {
        return QString();
    }
    return tokens.first().toLower();
}

bool verifySha256(const QString &filePath, const QString &expectedHex,
                  const QString &expectedFileName)
{
    QFile file(filePath);
    if (!file.open(QIODevice::ReadOnly)) {
        return false;
    }

    QCryptographicHash hash(QCryptographicHash::Sha256);
    while (!file.atEnd()) {
        const QByteArray chunk = file.read(1024 * 1024);
        if (chunk.isEmpty() && file.error() != QFileDevice::NoError) {
            return false;
        }
        hash.addData(chunk);
    }
    file.close();

    // release 的 .sha256 asset 必须是纯 hash 或标准 "<hash>  <filename>"。
    const QString expected =
        sha256FromManifest(expectedHex, expectedFileName);
    if (expected.isEmpty()) {
        return false;
    }
    return hash.result().toHex().compare(
               expected.toLatin1(), Qt::CaseInsensitive)
        == 0;
}

QString debianArchitecture()
{
    const QString architecture = QSysInfo::currentCpuArchitecture().toLower();
    if (architecture == QLatin1String("x86_64")
        || architecture == QLatin1String("amd64")) {
        return QStringLiteral("amd64");
    }
    if (architecture == QLatin1String("aarch64")
        || architecture == QLatin1String("arm64")) {
        return QStringLiteral("arm64");
    }
    return architecture;
}

bool parseRelease(const QByteArray &json, ReleaseInfo &out,
                  const QString &architecture)
{
    out = ReleaseInfo();

    QJsonParseError parseError;
    const QJsonDocument doc = QJsonDocument::fromJson(json, &parseError);
    if (parseError.error != QJsonParseError::NoError || !doc.isObject()) {
        return false;
    }

    const QJsonObject root = doc.object();
    const QString tagName = root.value(QLatin1String("tag_name")).toString();
    if (tagName.isEmpty()) {
        return false;
    }
    out.tag = normalizeVersion(tagName);
    if (!QRegularExpression(QStringLiteral("^\\d+\\.\\d+\\.\\d+$"))
             .match(out.tag)
             .hasMatch()
        || architecture.trimmed().isEmpty()) {
        return false;
    }
    out.architecture = architecture;
    out.debName = QStringLiteral("pixiu_%1-1_%2.deb")
                      .arg(out.tag, architecture);
    out.shaName = out.debName + QStringLiteral(".sha256");

    bool foundDeb = false;
    bool foundSha = false;
    const QJsonArray assets = root.value(QLatin1String("assets")).toArray();
    for (const QJsonValue &value : assets) {
        const QJsonObject asset = value.toObject();
        const QString name = asset.value(QLatin1String("name")).toString();
        const QString url =
            asset.value(QLatin1String("browser_download_url")).toString();

        if (name == out.debName) {
            if (foundDeb) {
                return false;
            }
            out.debUrl = url;
            foundDeb = true;
        } else if (name == out.shaName) {
            if (foundSha) {
                return false;
            }
            out.shaUrl = url;
            foundSha = true;
        }
    }

    if (!foundDeb || !foundSha || out.debUrl.isEmpty() || out.shaUrl.isEmpty()) {
        return false;
    }
    return true;
}

} // namespace ui
