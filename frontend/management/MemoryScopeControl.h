#pragma once
#include <QWidget>

class QComboBox;
class QPushButton;
namespace pixiu {
// Keeps existing scope values and change signals; adds an explicit custom choice.
class MemoryScopeControl : public QWidget
{
    Q_OBJECT
public:
    explicit MemoryScopeControl(QComboBox *combo);
protected:
    bool eventFilter(QObject *watched, QEvent *event) override;
private:
    void chooseScope();
    QComboBox *m_combo;
    QPushButton *m_custom;
};
}
