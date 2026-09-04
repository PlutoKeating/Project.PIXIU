#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
source_dir="${repo_root}/third_party/kylin-agent"
fixture="$(mktemp -d)"
trap 'rm -rf "${fixture}"' EXIT

expected_commit="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["components"]["kylin_agent"]["source_commit"])' "${repo_root}/build/release/agent-supply-chain-policy.json")"
test "$(git -C "${source_dir}" rev-parse HEAD)" = "${expected_commit}"

mkdir -p "${fixture}/source"
git -C "${source_dir}" archive --format=tar HEAD | tar -xf - -C "${fixture}/source"
patch -d "${fixture}/source" -p1 --forward --batch \
    < "${repo_root}/build/release/agent-host/patches/0001-build-coherent-offline-host.patch"
patch -d "${fixture}/source" -p1 --forward --batch \
    < "${repo_root}/build/release/agent-host/patches/0002-pixiu-premium-accessible-ui.patch"
install -D -m 0644 "${repo_root}/build/release/agent-host/compat/pixiu_host_compat.cpp" \
    "${fixture}/source/src/services/pixiu_host_compat.cpp"

# Exercise the same fail-closed source sanitization used by the real build.
python3 - "${fixture}/source" <<'PY'
from pathlib import Path
import re
import sys

root = Path(sys.argv[1])
gateway = root / "src/services/gatewayservice.cpp"
content = gateway.read_text(encoding="utf-8")
pattern = re.compile(r"(?i)\b(?:https?|git)://[^/\s:@]+:[^/\s@]+@[^\\\"\s]+")
content, count = pattern.subn("https://gitee.com/openkylin/kylin-cua.git", content)
test_count = count == 1
if not test_count:
    raise SystemExit(f"expected one authenticated upstream URL, found {count}")
gateway.write_text(content, encoding="utf-8")
for relative in ("scripts/agent_runtime_install.sh", "scripts/agent_runtime_install_bak.sh"):
    (root / relative).unlink()
for candidate in root.rglob("*"):
    if candidate.is_file() and pattern.search(candidate.read_text(encoding="utf-8", errors="ignore")):
        raise SystemExit(f"authenticated URL remains in {candidate.relative_to(root)}")
PY

grep -q 'src/services/pixiu_host_compat.cpp' "${fixture}/source/CMakeLists.txt"
grep -q 'GatewayService gatewayService' "${fixture}/source/src/main.cpp"
! grep -q 'src/ui/modelsettingswidget.cpp' "${fixture}/source/CMakeLists.txt"
grep -q '/v1/chat/completions' "${fixture}/source/src/services/pixiu_host_compat.cpp"
grep -q 'chatCompletionFinished' "${fixture}/source/src/services/pixiu_host_compat.cpp"
grep -q 'PIXIU · KylinAgent' "${fixture}/source/src/ui/mainwindow.cpp"
grep -q '分布式记忆工作台' "${fixture}/source/src/ui/mainwindow.cpp"
grep -q '选择云端模型' "${fixture}/source/src/ui/chatwidget.cpp"
grep -q 'DeepSeek Chat（官方云端）' "${fixture}/source/src/services/modelservice.cpp"
grep -q 'https://api.deepseek.com/v1' "${fixture}/source/src/services/modelservice.cpp"
grep -q 'providerPriority' "${fixture}/source/src/ui/chatwidget.cpp"
grep -q 'QStringLiteral("deepseek")' "${fixture}/source/src/ui/chatwidget.cpp"
! grep -q 'ModelProvider(QStringLiteral("ollama")' "${fixture}/source/src/services/modelservice.cpp"
! grep -q 'ModelProvider(QStringLiteral("lmstudio")' "${fixture}/source/src/services/modelservice.cpp"
! grep -q 'ModelProvider(QStringLiteral("openrouter")' "${fixture}/source/src/services/modelservice.cpp"
grep -q 'messageRole' "${fixture}/source/src/ui/chatwidget.cpp"
grep -q 'QWidget \*rowWidget = new QWidget(m_messagesContainer)' "${fixture}/source/src/ui/chatwidget.cpp"
grep -q 'm_messagesLayout->insertWidget(qMax(0, m_messagesLayout->count() - 1), rowWidget)' "${fixture}/source/src/ui/chatwidget.cpp"
! grep -q 'insertLayout(qMax(0, m_messagesLayout->count() - 1), row)' "${fixture}/source/src/ui/chatwidget.cpp"
grep -q 'delete item->widget()' "${fixture}/source/src/ui/chatwidget.cpp"
grep -q 'composerShell->setMaximumWidth(960)' "${fixture}/source/src/ui/chatwidget.cpp"
grep -q 'messageColumn->setMaximumWidth(920)' "${fixture}/source/src/ui/chatwidget.cpp"
grep -q 'row->addWidget(messageColumn, 20)' "${fixture}/source/src/ui/chatwidget.cpp"
grep -q 'messageAuthor' "${fixture}/source/src/ui/chatwidget.cpp"
grep -q '云端模型暂未响应' "${fixture}/source/src/ui/chatwidget.cpp"
grep -q 'legacyFallback' "${fixture}/source/src/ui/chatwidget.cpp"
grep -q 'setHorizontalScrollBarPolicy(Qt::ScrollBarAlwaysOff)' "${fixture}/source/src/ui/sessionlistwidget.cpp"
grep -q 'setTextElideMode(Qt::ElideRight)' "${fixture}/source/src/ui/sessionlistwidget.cpp"
grep -q '#066a75' "${fixture}/source/src/utils/thememanager.cpp"
grep -q '#41d3c4' "${fixture}/source/src/utils/thememanager.cpp"
! grep -q 'Database:' "${fixture}/source/src/ui/mainwindow.cpp"
! grep -q 'setStyleSheet' "${fixture}/source/src/ui/mainwindow.cpp"
! grep -q 'setStyleSheet' "${fixture}/source/src/ui/sidebar.cpp"
! grep -q 'setStyleSheet' "${fixture}/source/src/ui/chatwidget.cpp"
! grep -q 'setStyleSheet' "${fixture}/source/src/ui/sessionlistwidget.cpp"
grep -q -- '--hide' "${repo_root}/build/release/agent-host/build-agent-host.sh"
! grep -q -- 'kylin-agent.*--version' "${repo_root}/build/release/agent-host/build-agent-host.sh"

echo "agent host adaptation tests: OK"
