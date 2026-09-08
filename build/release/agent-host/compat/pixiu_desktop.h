#pragma once

// One host, two desktop adapters. Portable builds do not emulate SDK results.
#ifdef PIXIU_HAVE_KYSDK
#include <kdialog.h>
#include <kinputdialog.h>
#include <kmessagebox.h>

namespace pixiu::desktop {
class Dialog : public kdk::KDialog
{
public:
    explicit Dialog(QWidget *parent = nullptr) : kdk::KDialog(parent)
    {
        // The SDK icon follows the system theme, which can differ from the host.
        // Keep the SDK button and its close connection; render its mark as text
        // using the host palette. A later SDK icon refresh must not add an icon.
        auto *close = closeButton();
        close->setIcon(QIcon());
        close->setIconSize(QSize(0, 0));
        close->setText(QString::fromUtf8("×"));
        close->setToolTip(QStringLiteral("关闭"));
        close->setAccessibleName(QStringLiteral("关闭"));
    }
};
using InputDialog = kdk::KInputDialog;
using MessageBox = kdk::KMessageBox;
}
#else
#include <QDialog>
#include <QInputDialog>
#include <QMessageBox>

namespace pixiu::desktop {
class Dialog : public QDialog
{
public:
    using QDialog::QDialog;
    QWidget *mainWidget() { return this; }
};
using InputDialog = QInputDialog;
using MessageBox = QMessageBox;
}
#endif
