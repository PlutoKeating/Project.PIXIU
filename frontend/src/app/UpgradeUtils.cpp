#include "app/UpgradeUtils.h"

#include <QCryptographicHash>
#include <QFile>
#include <QJsonArray>
#include <QJsonDocument>
#include <QJsonObject>
#include <QJsonParseError>
#include <QStringList>
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

bool verifySha256(const QString &filePath, const QString &expectedHex)
{
    QFile file(filePath);
    if (!file.open(QIODevice::ReadOnly)) {
        return false;
    }
    const QByteArray data = file.readAll();
    file.close();

    // release 的 .sha256 asset 内容常为 "<hash>  <filename>"，取首个空白
    // 分隔 token；纯 hex 入参原样比较；大小写不敏感。
    const QString expected =
        expectedHex.trimmed().section(QLatin1Char(' '), 0, 0);
    return sha256Hex(data).compare(expected.toLatin1(), Qt::CaseInsensitive) == 0;
}

bool parseRelease(const QByteArray &json, ReleaseInfo &out)
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

    bool foundDeb = false;
    bool foundSha = false;
    const QJsonArray assets = root.value(QLatin1String("assets")).toArray();
    for (const QJsonValue &value : assets) {
        const QJsonObject asset = value.toObject();
        const QString name = asset.value(QLatin1String("name")).toString();
        const QString url =
            asset.value(QLatin1String("browser_download_url")).toString();

        if (name.startsWith(QLatin1String("pixiu_"))
            && name.endsWith(QLatin1String("-1_amd64.deb"))) {
            out.debUrl = url;
            foundDeb = true;
        } else if (name.endsWith(QLatin1String(".deb.sha256"))) {
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
