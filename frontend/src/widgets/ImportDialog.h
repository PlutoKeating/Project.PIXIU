#ifndef PIXIU_IMPORT_DIALOG_H
#define PIXIU_IMPORT_DIALOG_H

#include <QDialog>

class QLineEdit;
class QPlainTextEdit;
class QComboBox;

// 记忆录入对话框：标题 + 内容 + 作用域，确认后发射 importRequested。
//
// Phase 4.2 将扩展图片拖入与录入预览。
class ImportDialog : public QDialog
{
    Q_OBJECT

public:
    explicit ImportDialog(QWidget *parent = nullptr);

signals:
    void importRequested(const QString &title,
                         const QString &content,
                         const QString &scope);

private:
    void onConfirmClicked();

    QLineEdit *m_titleEdit = nullptr;
    QPlainTextEdit *m_contentEdit = nullptr;
    QComboBox *m_scopeCombo = nullptr;
};

#endif // PIXIU_IMPORT_DIALOG_H
