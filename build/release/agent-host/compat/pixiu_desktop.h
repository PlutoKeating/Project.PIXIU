#pragma once

// One host, two desktop adapters. Portable builds do not emulate SDK results.
#ifdef PIXIU_HAVE_KYSDK
#include <kdialog.h>
#include <kinputdialog.h>
#include <kmessagebox.h>

namespace pixiu::desktop {
using Dialog = kdk::KDialog;
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
