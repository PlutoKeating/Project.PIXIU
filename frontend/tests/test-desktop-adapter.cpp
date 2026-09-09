#include "pixiu_desktop.h"
#include <QApplication>
#include <QPushButton>
#include <QTimer>
#include <QVBoxLayout>

int main(int argc, char **argv)
{
    QApplication app(argc, argv);
    pixiu::desktop::Dialog dialog;
    auto *layout = new QVBoxLayout(dialog.mainWidget());
    layout->addWidget(new QPushButton(QStringLiteral("Content"), dialog.mainWidget()));
    QTimer::singleShot(0, &dialog, &QDialog::accept);
    if (dialog.exec() != QDialog::Accepted || !dialog.mainWidget()->layout())
        return 1;

    pixiu::desktop::InputDialog input;
    input.setInputMode(pixiu::desktop::InputDialog::TextInput);
    input.setTextValue(QStringLiteral("PIXIU"));
    QTimer::singleShot(0, &input, &QDialog::reject);
    if (input.exec() != QDialog::Rejected || input.textValue() != QStringLiteral("PIXIU"))
        return 2;

    pixiu::desktop::MessageBox confirmation;
    confirmation.setIcon(pixiu::desktop::MessageBox::Question);
    auto *accept = confirmation.addButton(QStringLiteral("Confirm"), pixiu::desktop::MessageBox::AcceptRole);
    auto *reject = confirmation.addButton(QStringLiteral("Cancel"), pixiu::desktop::MessageBox::RejectRole);
    QTimer::singleShot(0, reject, &QPushButton::click);
    confirmation.exec();
    if (confirmation.clickedButton() != reject || confirmation.clickedButton() == accept)
        return 3;
    return 0;
}
