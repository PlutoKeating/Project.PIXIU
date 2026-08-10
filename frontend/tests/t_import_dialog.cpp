#include <QComboBox>
#include <QDialogButtonBox>
#include <QDropEvent>
#include <QImage>
#include <QLabel>
#include <QLineEdit>
#include <QMimeData>
#include <QPlainTextEdit>
#include <QPushButton>
#include <QSignalSpy>
#include <QTemporaryDir>
#include <QTest>
#include <QUrl>

#include "widgets/ImportDialog.h"

// ImportDialog 测试：确认按钮门控、提交载荷、取消/Esc 隐藏、图片拖入预览。
// Qt 的拖放事件由 QApplication 内部特殊派发，sendEvent 不会送达 dropEvent，
// 因此测试子类直接暴露受保护的 dropEvent 进行逻辑验证。
class TestableImportDialog : public ImportDialog
{
public:
    using ImportDialog::dropEvent;
};

class TestImportDialog : public QObject
{
    Q_OBJECT

private slots:
    void okButtonRequiresTitleAndContent();
    void confirmEmitsImportRequestedAndClears();
    void cancelHidesDialog();
    void escHidesDialog();
    void imageDropSetsPreviewAndPayload();
};

static QPushButton *buttonOf(QDialogButtonBox::StandardButton which, ImportDialog *dialog)
{
    QDialogButtonBox *box = dialog->findChild<QDialogButtonBox *>();
    return box ? box->button(which) : nullptr;
}

void TestImportDialog::okButtonRequiresTitleAndContent()
{
    ImportDialog dialog;
    QPushButton *ok = buttonOf(QDialogButtonBox::Ok, &dialog);
    QVERIFY(ok != nullptr);
    QVERIFY(!ok->isEnabled());

    QLineEdit *title = dialog.findChild<QLineEdit *>();
    QPlainTextEdit *content = dialog.findChild<QPlainTextEdit *>();
    QVERIFY(title != nullptr);
    QVERIFY(content != nullptr);

    title->setText(QStringLiteral("2026年4月家庭支出清单"));
    QVERIFY(!ok->isEnabled());

    content->setPlainText(QStringLiteral("电费 210 元"));
    QVERIFY(ok->isEnabled());

    content->clear();
    QVERIFY(!ok->isEnabled());
}

void TestImportDialog::confirmEmitsImportRequestedAndClears()
{
    ImportDialog dialog;
    QSignalSpy spy(&dialog, &ImportDialog::importRequested);

    QLineEdit *title = dialog.findChild<QLineEdit *>();
    QPlainTextEdit *content = dialog.findChild<QPlainTextEdit *>();
    QComboBox *scope = dialog.findChild<QComboBox *>();
    QVERIFY(scope != nullptr);
    title->setText(QStringLiteral("  清单  "));
    content->setPlainText(QStringLiteral("  电费 210 元  "));

    QPushButton *ok = buttonOf(QDialogButtonBox::Ok, &dialog);
    QTest::mouseClick(ok, Qt::LeftButton);

    QCOMPARE(spy.count(), 1);
    const QList<QVariant> args = spy.takeFirst();
    QCOMPARE(args.at(0).toString(), QStringLiteral("清单"));
    QCOMPARE(args.at(1).toString(), QStringLiteral("电费 210 元"));
    QCOMPARE(args.at(2).toString(), QStringLiteral("user:local"));
    QCOMPARE(args.at(3).toString(), QString());
    QVERIFY(!dialog.isVisible());
    QVERIFY(title->text().isEmpty());
    QVERIFY(content->toPlainText().isEmpty());
}

void TestImportDialog::cancelHidesDialog()
{
    ImportDialog dialog;
    dialog.show();
    QVERIFY(dialog.isVisible());

    QPushButton *cancel = buttonOf(QDialogButtonBox::Cancel, &dialog);
    QTest::mouseClick(cancel, Qt::LeftButton);
    QVERIFY(!dialog.isVisible());
}

void TestImportDialog::escHidesDialog()
{
    ImportDialog dialog;
    dialog.show();
    QVERIFY(dialog.isVisible());

    QTest::keyClick(&dialog, Qt::Key_Escape);
    QVERIFY(!dialog.isVisible());
}

void TestImportDialog::imageDropSetsPreviewAndPayload()
{
    QTemporaryDir dir;
    QVERIFY(dir.isValid());
    const QString path = dir.filePath(QStringLiteral("drop.png"));
    QImage image(8, 8, QImage::Format_RGB32);
    image.fill(Qt::red);
    QVERIFY(image.save(path));

    TestableImportDialog dialog;
    QMimeData mime;
    mime.setUrls({QUrl::fromLocalFile(path)});
    QDropEvent drop(QPointF(10, 10), Qt::CopyAction, &mime,
                    Qt::LeftButton, Qt::NoModifier);
    dialog.dropEvent(&drop);

    QLabel *preview =
        dialog.findChild<QLabel *>(QStringLiteral("previewLabel"));
    QVERIFY(preview != nullptr);
    QVERIFY(!preview->pixmap(Qt::ReturnByValue).isNull());

    dialog.findChild<QLineEdit *>()->setText(QStringLiteral("拖入图片"));
    dialog.findChild<QPlainTextEdit *>()->setPlainText(QStringLiteral("内容"));

    QSignalSpy spy(&dialog, &ImportDialog::importRequested);
    QTest::mouseClick(buttonOf(QDialogButtonBox::Ok, &dialog), Qt::LeftButton);

    QCOMPARE(spy.count(), 1);
    QCOMPARE(spy.takeFirst().at(3).toString(), path);
}

QTEST_MAIN(TestImportDialog)
#include "t_import_dialog.moc"
