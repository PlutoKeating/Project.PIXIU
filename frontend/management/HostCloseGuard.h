#pragma once
#include <QObject>
#include <functional>
class QWidget;
class QDialog;

namespace pixiu {
// One guard belongs to the Agent host; embedded pages do not own application exit.
class HostCloseGuard : public QObject
{
    Q_OBJECT
public:
    explicit HostCloseGuard(QWidget *host,
        std::function<bool()> agentPending = {}, std::function<bool()> agentDraft = {});
    // A successful upgrade asks before scheduling its restart helper.
    bool confirmExit(const QDialog *initiatingDialog = nullptr);
protected:
    bool eventFilter(QObject *watched, QEvent *event) override;
private:
    QWidget *m_host;
    std::function<bool()> m_agentPending, m_agentDraft;
    bool m_checking = false;
};
}
