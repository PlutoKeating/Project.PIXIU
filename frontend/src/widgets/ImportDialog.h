#ifndef PIXIU_IMPORT_DIALOG_H
#define PIXIU_IMPORT_DIALOG_H

#include <QDialog>

class QLineEdit;
class QPlainTextEdit;
class QComboBox;
class QLabel;

    // 记忆录入对话框：标题 + 内容 + 作用域 + 图片拖入预览，确认后发射 importRequested。
class ImportDialog : public QDialog
{
    Q_OBJECT

public:
    explicit ImportDialog(QWidget *parent = nullptr);

signals:
    void importRequested(const QString &title,
                         const QString &content,
                         const QString &scope,
                         const QString &imagePath);

protected:
    void dragEnterEvent(QDragEnterEvent *event) override;
    void dropEvent(QDropEvent *event) override;

private:
    void onConfirmClicked();
    void setPreviewImage(const QString &path);

    QLineEdit *m_titleEdit = nullptr;
    QPlainTextEdit *m_contentEdit = nullptr;
    QComboBox *m_scopeCombo = nullptr;
    QLabel *m_previewLabel = nullptr;
    QString m_imagePath;
};

#endif // PIXIU_IMPORT_DIALOG_H
