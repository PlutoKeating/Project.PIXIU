#include <QCoreApplication>
#include <QLabel>
#include <QPushButton>
#include <QTest>
#include <QTextBrowser>

#include "widgets/CheckUpdateDialog.h"
#include "widgets/InfoDialog.h"

// Shared dialogs retained by the sole host, independent of retired settings UI.
class TestProductDialogs : public QObject
{
    Q_OBJECT

private slots:
    void initTestCase()
    {
        QCoreApplication::setApplicationVersion(QStringLiteral(PIXIU_VERSION));
    }

    void infoDialogRendersTitleAndBodyReadOnly()
    {
        const QString title = QStringLiteral("说明测试");
        const QString body = QStringLiteral("第一段 <b>纯文本</b>\n\n第二段 & 原样显示");
        InfoDialog dialog(title, body);
        QCOMPARE(dialog.windowTitle(), title);
        auto *browser = dialog.findChild<QTextBrowser *>(QStringLiteral("infoTextBrowser"));
        QVERIFY(browser);
        QVERIFY(browser->isReadOnly());
        QCOMPARE(browser->toPlainText(), body);
        QCOMPARE(dialog.windowModality(), Qt::NonModal);
    }

    void infoDialogCloseOnlyClosesItself()
    {
        QWidget host;
        InfoDialog dialog(QStringLiteral("说明"), QStringLiteral("正文"), &host);
        auto *close = dialog.findChild<QPushButton *>(QStringLiteral("infoCloseButton"));
        QVERIFY(close);
        QVERIFY(!close->accessibleName().isEmpty());
        host.show();
        dialog.showAndFocus();
        QVERIFY(dialog.isVisible());
        QTest::mouseClick(close, Qt::LeftButton);
        QVERIFY(!dialog.isVisible());
        QVERIFY(host.isVisible());
    }

    void checkUpdateDialogShowsCurrentVersionAndGuide()
    {
        CheckUpdateDialog dialog;
        auto *current = dialog.findChild<QLabel *>(QStringLiteral("currentVersionLabel"));
        QVERIFY(current);
        QVERIFY(current->text().contains(QCoreApplication::applicationVersion()));
        auto *upgrade = dialog.findChild<QPushButton *>(QStringLiteral("upgradeButton"));
        QVERIFY(upgrade);
        QVERIFY(!upgrade->isEnabled());
        QCOMPARE(dialog.controller(), nullptr);
        QCOMPARE(dialog.windowModality(), Qt::NonModal);
        auto *close = dialog.findChild<QPushButton *>(QStringLiteral("closeButton"));
        QVERIFY(close);
        dialog.show();
        QTest::mouseClick(close, Qt::LeftButton);
        QVERIFY(!dialog.isVisible());
    }
};

QTEST_MAIN(TestProductDialogs)
#include "t_product_dialogs.moc"
