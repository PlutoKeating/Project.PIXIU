#include "MemoryEditDialog.h"
#include "services/HttpBackendTransport.h"
#include <QLabel>
#include <QLineEdit>
#include <QPlainTextEdit>
#include <QPushButton>
#include <QSignalSpy>
#include <QTest>

class LiveEditTest : public QObject
{
    Q_OBJECT
private slots:
    void updateAndConflictAgainstBackend()
    {
        if (qEnvironmentVariable("PIXIU_MANAGEMENT_LIVE_TEST") != "1")
            QSKIP("Run through run-memory-edit-live.py to provision an isolated backend");
        const auto id = qEnvironmentVariable("PIXIU_LIVE_KNOWLEDGE_ID");
        QVERIFY(!id.isEmpty());
        const QString scope = QStringLiteral("user:ui_test");
        pixiu::MemoryEditDialog editor(nullptr);
        auto *title = editor.findChild<QLineEdit *>("editTitle");
        auto *body = editor.findChild<QPlainTextEdit *>("editBody");
        auto *save = editor.findChild<QPushButton *>("editSave");
        auto *status = editor.findChild<QLabel *>("editStatus");
        QSignalSpy changed(&editor, &pixiu::MemoryEditDialog::memoryUpdated);
        editor.openMemory(id, scope);
        QTRY_VERIFY_WITH_TIMEOUT(title->isEnabled(), 15000);
        QCOMPARE(body->toPlainText(), QStringLiteral("before live edit"));
        title->setText("edited by real Qt dialog");
        body->setPlainText("after live edit\n第二行 {plain text}");
        QVERIFY(save->isEnabled());
        save->click();
        QTRY_COMPARE_WITH_TIMEOUT(changed.count(), 1, 15000);
        QVERIFY(!save->isEnabled());

        HttpBackendTransport verifier;
        QSignalSpy fetched(&verifier, &BackendTransport::memoryItemResult);
        verifier.memoryItem(id, scope);
        QTRY_COMPARE_WITH_TIMEOUT(fetched.count(), 1, 15000);
        const auto stored = fetched.first().first().toJsonObject();
        QCOMPARE(stored.value("title").toString(), QStringLiteral("edited by real Qt dialog"));
        QCOMPARE(stored.value("version").toInt(), 2);
        QCOMPARE(stored.value("body").toObject().value("text").toString(), body->toPlainText());
        QCOMPARE(stored.value("body").toObject().value("metadata").toObject(), QJsonObject({{"keep", true}}));

        editor.findChild<QPushButton *>("editReload")->click();
        QTRY_VERIFY_WITH_TIMEOUT(title->isEnabled(), 15000);
        title->setText("unsaved local draft");
        QSignalSpy otherUpdated(&verifier, &BackendTransport::memoryUpdated);
        verifier.updateMemory({{"knowledge_id", id}, {"scope", scope}, {"expected_version", 2},
            {"title", "other editor wins"}, {"idempotency_key", "live-other-editor"}});
        QTRY_COMPARE_WITH_TIMEOUT(otherUpdated.count(), 1, 15000);
        save->click();
        QTRY_VERIFY_WITH_TIMEOUT(status->text().contains("VERSION_CONFLICT"), 15000);
        QCOMPARE(title->text(), QStringLiteral("unsaved local draft"));
        QCOMPARE(changed.count(), 1);
        QVERIFY(!save->isEnabled());
        verifier.memoryItem(id, scope);
        QTRY_COMPARE_WITH_TIMEOUT(fetched.count(), 2, 15000);
        const auto winner = fetched.last().first().toJsonObject();
        QCOMPARE(winner.value("title").toString(), QStringLiteral("other editor wins"));
        QCOMPARE(winner.value("version").toInt(), 3);
        QCOMPARE(winner.value("body"), stored.value("body"));
    }
};
QTEST_MAIN(LiveEditTest)
#include "t_memory_edit_live.moc"
