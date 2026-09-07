#pragma once
#include <QComboBox>
#include <QRegularExpression>

namespace pixiu {
// Values are existing data domains, not aliases to merge or authorization roles.
inline void populateMemoryScopes(QComboBox *combo, bool includeAll,
    bool preferPrivateAgent = false,
    const QString &agentScope = qEnvironmentVariable("PIXIU_AGENT_SCOPE"))
{
    if (includeAll) combo->addItem(QObject::tr("全部范围"), QString());
    combo->addItem(QObject::tr("本机个人记忆（含采集）"), QStringLiteral("user:local"));
    combo->addItem(QObject::tr("家庭共享"), QStringLiteral("shared:home"));
    const QRegularExpression valid(QStringLiteral("\\A(user|shared):[A-Za-z0-9._-]+\\z"));
    if (!valid.match(agentScope).hasMatch()) return;
    int index = combo->findData(agentScope);
    const QString label = QObject::tr("Agent 记忆（%1）").arg(agentScope);
    if (index < 0) {
        combo->addItem(label, agentScope);
        index = combo->count() - 1;
    } else {
        combo->setItemText(index, combo->itemText(index) + QObject::tr(" · Agent 当前范围"));
    }
    // A shared Agent profile must never turn manual capture into implicit sharing.
    if (preferPrivateAgent && agentScope.startsWith(QStringLiteral("user:")))
        combo->setCurrentIndex(index);
}
}
