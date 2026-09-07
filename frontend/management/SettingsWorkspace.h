#pragma once
#include <QWidget>
namespace pixiu {
class SettingsWorkspace : public QWidget
{
    Q_OBJECT
public:
    explicit SettingsWorkspace(QWidget *parent = nullptr);
signals:
    void agentSettingsRequested();
};
}
