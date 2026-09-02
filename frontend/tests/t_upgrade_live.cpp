#include <QCoreApplication>
#include <QLabel>
#include <QProcess>
#include <QPushButton>
#include <QSignalSpy>
#include <QTest>

#include <functional>

#include "app/UpgradeController.h"
#include "widgets/CheckUpdateDialog.h"

// 本机验收：真实 GitHub releases/latest + 应用内 CheckUpdateDialog +
// 与生产相同的 /usr/lib/pixiu/install-update 参数（经 sudo -n，避免无人值守
// 会话卡住 polkit 图形授权）。默认跳过，避免 CI 打 GitHub / 改本机软件包。
//
// 运行：
//   PIXIU_LIVE_UPGRADE=1 PIXIU_LIVE_UPGRADE_INSTALL=1 \
//     ./t_upgrade_live
class TestUpgradeLive : public QObject
{
    Q_OBJECT

private slots:
    void initTestCase();
    void githubDialogCheckAndInstall();
};

void TestUpgradeLive::initTestCase()
{
    qRegisterMetaType<UpgradeController::State>("UpgradeController::State");
    qRegisterMetaType<UpgradeController::FailedReason>("FailedReason");
}

void TestUpgradeLive::githubDialogCheckAndInstall()
{
    if (qgetenv("PIXIU_LIVE_UPGRADE") != QByteArrayLiteral("1")) {
        QSKIP("set PIXIU_LIVE_UPGRADE=1 to run GitHub in-app upgrade acceptance");
    }

    // 已安装包与 latest 同为 0.1.6 时，生产 UI 会走 UpToDate。验收必须把
    // 本地版本压到更低，才能走下载/校验/安装；资产仍是公开发布的 latest。
    QCoreApplication::setApplicationVersion(QStringLiteral("0.1.5"));

    UpgradeController controller;
    const bool doInstall =
        qgetenv("PIXIU_LIVE_UPGRADE_INSTALL") == QByteArrayLiteral("1");
    if (doInstall) {
        controller.setInstallRunner(
            [](const QString &, const QStringList &args,
               const std::function<void(int)> &done) {
                QProcess proc;
                QStringList sudoArgs;
                sudoArgs << QStringLiteral("-n");
                sudoArgs.append(args);
                proc.start(QStringLiteral("/usr/bin/sudo"), sudoArgs);
                if (!proc.waitForFinished(600000)) {
                    proc.kill();
                    done(-1);
                    return;
                }
                done(proc.exitCode());
            });
    } else {
        controller.setInstallRunner(
            [](const QString &, const QStringList &,
               const std::function<void(int)> &done) { done(0); });
    }

    CheckUpdateDialog dialog(&controller);
    dialog.showAndCheck();

    QPushButton *upgrade = dialog.findChild<QPushButton *>(
        QStringLiteral("upgradeButton"));
    QVERIFY(upgrade != nullptr);
    QTRY_VERIFY_WITH_TIMEOUT(upgrade->isEnabled(), 120000);

    QLabel *remote = dialog.findChild<QLabel *>(
        QStringLiteral("remoteVersionLabel"));
    QVERIFY(remote != nullptr);
    QVERIFY(remote->text().contains(QStringLiteral("0.1.6")));

    QSignalSpy finished(&controller, &UpgradeController::upgradeFinished);
    QTest::mouseClick(upgrade, Qt::LeftButton);

    QTRY_VERIFY_WITH_TIMEOUT(finished.count() >= 1, 600000);
    QCOMPARE(controller.state(), UpgradeController::State::Success);
    const QList<QVariant> row = finished.takeFirst();
    QCOMPARE(row.at(0).toBool(), true);
}

QTEST_MAIN(TestUpgradeLive)
#include "t_upgrade_live.moc"
