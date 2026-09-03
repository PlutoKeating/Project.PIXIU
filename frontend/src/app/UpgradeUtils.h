#ifndef PIXIU_UPGRADE_UTILS_H
#define PIXIU_UPGRADE_UTILS_H

#include <QByteArray>
#include <QString>

// 版本比较 + sha256 校验 + GitHub release 解析（纯函数，无 UI / 无网络）。
//
// 命名空间选择：沿用应用层 `ui`（与 UserIdentity / Severity / UiTokens 一致）。
// 设计与计划文档（docs/compose/plans/2026-09-01-in-app-upgrade.md）曾以
// `pixiu` 命名这些函数，但仓库中 `pixiu` 命名空间目前专用于 UkuiWindow 的
// 平台/窗口装饰（decorateUkuiWindow / ukuiWindowAvailable），而版本比较与
// 哈希这类纯工具与 ui::parseSeverity、ui::displayUserName 同族（均为 app/ 下
// 无 UI 依赖的纯函数），故归 `ui` 以便后续 UpgradeController 统一引用。
namespace ui {

// 去掉版本 tag 的前缀 `v`："v0.1.6" → "0.1.6"；无 `v` 前缀则原样返回。
QString normalizeVersion(const QString &tag);

// 按 `.` 分段转整数比较，返回 -1/0/1。缺段视为 0：
//   "0.1.6" == "0.1.6.0"；"0.1.6.1" > "0.1.6"；"1.2" == "1.2.0"。
// 非数字段防御性按 0（版本号保证纯数字）。
int compareVersions(const QString &a, const QString &b);

// QCryptographicHash::Sha256 的小写十六进制字符串。
QByteArray sha256Hex(const QByteArray &data);

// 解析标准 sha256sum 清单并可绑定目标资产文件名；非法时返回空字符串。
QString sha256FromManifest(const QString &manifest,
                           const QString &expectedFileName = QString());

// 读文件重算 sha256 并与 expectedHex 比对（大小写不敏感）。
// 文件不存在 / 读失败返回 false。
// expectedFileName 非空时，同时要求 .sha256 中的文件名与目标资产一致。
bool verifySha256(const QString &filePath, const QString &expectedHex,
                  const QString &expectedFileName = QString());

// 将 Qt CPU 架构名映射为 Debian 架构名（x86_64→amd64、aarch64→arm64）。
QString debianArchitecture();

// GitHub releases/latest 响应解析结果。
struct ReleaseInfo {
    QString tag;     // strip 'v' 后的版本号（如 0.1.6）
    QString debUrl;  // pixiu_<ver>-1_amd64.deb 的 browser_download_url
    QString shaUrl;  // 同名 .deb.sha256 的 browser_download_url
    QString sigUrl;  // 同名 .deb.sha256.sig 的 browser_download_url
    QString debName;
    QString shaName;
    QString sigName;
    QString architecture;
};

// 解析 GitHub releases/latest JSON：
//   取 tag_name（strip 'v'）；在 assets[].name 中找
//   严格匹配 tag + 当前 Debian 架构的同名 .deb / .deb.sha256 资产。
// 缺任一字段、资产错配、URL 为空或 JSON 非法返回 false。
bool parseRelease(const QByteArray &json, ReleaseInfo &out,
                  const QString &architecture = debianArchitecture());

} // namespace ui

#endif // PIXIU_UPGRADE_UTILS_H
