#include "HostCloseGuard.h"
#include "PrivacyPage.h"
#include "DevicePage.h"
#include "ForgetPage.h"
#include "MemoryAudit.h"
#include "MemoryWorkspace.h"
#include "DeliveryPage.h"
#include "ServiceStatusPage.h"
#include "AgentEvidenceClient.h"
#include <QAbstractButton>
#include <QCloseEvent>
#include <QDialog>
#include <QMessageBox>
#include <QScopedValueRollback>
#include <QWidget>
#include <utility>

namespace pixiu {
HostCloseGuard::HostCloseGuard(QWidget *host,
    std::function<bool()> agentPending, std::function<bool()> agentDraft)
    : QObject(host), m_host(host), m_agentPending(std::move(agentPending)),
      m_agentDraft(std::move(agentDraft))
{
    host->installEventFilter(this);
}

bool HostCloseGuard::eventFilter(QObject *watched, QEvent *event)
{
    if (watched != m_host || event->type() != QEvent::Close)
        return QObject::eventFilter(watched, event);
    auto *close = static_cast<QCloseEvent *>(event);
    close->ignore();
    if (!confirmExit()) return true;
    close->accept();
    return false;
}

bool HostCloseGuard::hasPendingOperation() const
{
    if (m_agentPending && m_agentPending()) return true;
    for (auto *client : m_host->findChildren<AgentEvidenceClient *>())
        if (client->busy()) return true;
    for (auto *page : m_host->findChildren<PrivacyPage *>())
        if (page->hasPendingOperation()) return true;
    for (auto *page : m_host->findChildren<DevicePage *>())
        if (page->hasPendingOperation()) return true;
    for (auto *page : m_host->findChildren<ForgetPage *>())
        if (page->hasPendingOperation()) return true;
    for (auto *page : m_host->findChildren<MemoryAudit *>())
        if (page->hasPendingOperation()) return true;
    for (auto *page : m_host->findChildren<MemoryWorkspace *>())
        if (page->hasPendingOperation()) return true;
    for (auto *page : m_host->findChildren<DeliveryPage *>())
        if (page->hasPendingOperation()) return true;
    for (auto *page : m_host->findChildren<ServiceStatusPage *>())
        if (page->hasPendingOperation()) return true;
    return false;
}

bool HostCloseGuard::confirmExit(const QDialog *initiatingDialog)
{
    if (m_checking) return false;
    QScopedValueRollback<bool> checking(m_checking, true);
    // Do not bypass a dialog's own save/cancel/install safety boundary.
    for (auto *dialog : m_host->findChildren<QDialog *>()) {
        if (dialog == initiatingDialog || !dialog->isVisible()) continue;
        dialog->raise();
        dialog->activateWindow();
        return false;
    }
    bool unsaved = m_agentDraft && m_agentDraft();
    for (auto *page : m_host->findChildren<PrivacyPage *>()) {
        unsaved |= page->hasUnsavedChanges();
    }
    for (auto *page : m_host->findChildren<DevicePage *>()) {
        unsaved |= page->hasUnsavedChanges();
    }
    if (hasPendingOperation()) {
        QMessageBox::information(m_host, tr("暂不能退出"),
            tr("管理操作或 Agent 请求正在等待结果，请待操作完成或报告失败后再退出。关闭窗口不会取消已提交的后端操作。"));
        return false;
    }
    if (unsaved) {
        QMessageBox question(QMessageBox::Warning, tr("编辑尚未保存"),
            tr("配置有未保存的修改，或会话中有未发送的输入。是否放弃这些编辑并退出？不会发送草稿或修改后端已保存的配置。"),
            QMessageBox::Yes | QMessageBox::No, m_host);
        question.button(QMessageBox::No)->setText(tr("保留编辑"));
        question.button(QMessageBox::Yes)->setText(tr("放弃并退出"));
        question.setDefaultButton(QMessageBox::No);
        question.setEscapeButton(QMessageBox::No);
        if (question.exec() != QMessageBox::Yes) return false;
    }
    // A modal confirmation runs an event loop: consult all live request state again.
    return !hasPendingOperation();
}
}
