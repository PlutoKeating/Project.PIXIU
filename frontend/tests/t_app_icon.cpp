#include <QIcon>
#include <QPixmap>
#include <QTest>

// 应用图标资源测试：验证 qrc 内嵌 pixiu.svg 可加载且能渲染出有效像素。
class TestAppIcon : public QObject
{
    Q_OBJECT

private slots:
    void iconResourceLoads();
    void iconHasContent();
};

void TestAppIcon::iconResourceLoads()
{
    QIcon icon(QStringLiteral(":/icons/pixiu.svg"));
    QVERIFY(!icon.isNull());
}

void TestAppIcon::iconHasContent()
{
    QIcon icon(QStringLiteral(":/icons/pixiu.svg"));
    const QPixmap pixmap = icon.pixmap(64, 64);
    QVERIFY(!pixmap.isNull());
    QVERIFY(pixmap.width() > 0);
    QVERIFY(pixmap.height() > 0);
}

QTEST_MAIN(TestAppIcon)
#include "t_app_icon.moc"
