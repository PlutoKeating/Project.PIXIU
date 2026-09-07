#include "HostCloseGuard.h"
#include "PrivacyPage.h"
#include "DevicePage.h"
#include "ForgetPage.h"
#include "MemoryAudit.h"
#include <QCloseEvent>
#include <QDialog>
#include <QMessageBox>
#include <QScopedValueRollback>
#include <QWidget>

namespace pixiu {
HostCloseGuard::HostCloseGuard(QWidget *host) : QObject(host), m_host(host)
{
    host->installEventFilter(this);
}

bool HostCloseGuard::eventFilter(QObject *watched, QEvent *event)
{
    if (watched != m_host || event->type() != QEvent::Close)
        return QObject::eventFilter(watched, event);
    auto *close = static_cast<QCloseEvent *>(event);
    close->ignore();
    if (m_checking) return true;
    QScopedValueRollback<bool> checking(m_checking, true);
    // Do not bypass a dialog's own save/cancel/install safety boundary.
    for (auto *dialog : m_host->findChildren<QDialog *>()) {
        if (!dialog->isVisible()) continue;
        dialog->raise();
        dialog->activateWindow();
        return true;
    }
    bool pending = false;
    bool unsaved = false;
    for (auto *page : m_host->findChildren<PrivacyPage *>()) {
        pending |= page->hasPendingOperation();
        unsaved |= page->hasUnsavedChanges();
    }
    for (auto *page : m_host->findChildren<DevicePage *>()) {
        pending |= page->hasPendingOperation();
        unsaved |= page->hasUnsavedChanges();
    }
    for (auto *page : m_host->findChildren<ForgetPage *>())
        pending |= page->hasPendingOperation();
    for (auto *page : m_host->findChildren<MemoryAudit *>())
        pending |= page->hasPendingOperation();
    if (pending) {
        QMessageBox::information(m_host, tr("暂不能退出"),
            tr("管理操作正在等待结果，请待操作完成或报告失败后再退出。关闭窗口不会取消已提交的后端操作。"));
        return true;
    }
    if (unsaved) {
        QMessageBox question(QMessageBox::Warning, tr("配置尚未保存"),
            tr("采集或同步设置有未保存的修改。是否放弃这些编辑并退出？不会修改后端已保存的配置。"),
            QMessageBox::Yes | QMessageBox::No, m_host);
        question.setDefaultButton(QMessageBox::No);
        question.setEscapeButton(QMessageBox::No);
        if (question.exec() != QMessageBox::Yes) return true;
    }
    close->accept();
    return false;
}
}
