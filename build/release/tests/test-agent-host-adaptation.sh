#!/usr/bin/env bash
set -euo pipefail

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
fixture="$(mktemp -d)"
trap 'rm -rf "${fixture}"' EXIT

mkdir -p "${fixture}/source"
bash "${repo_root}/build/release/agent-host/prepare-agent-host.sh" "${fixture}/source"

# A second preparation must reject existing source, without overwriting it.
prepared_hash="$(sha256sum "${fixture}/source/CMakeLists.txt")"
if bash "${repo_root}/build/release/agent-host/prepare-agent-host.sh" "${fixture}/source"; then
    echo "source preparation unexpectedly accepted nonempty destination" >&2
    exit 1
fi
test "$(sha256sum "${fixture}/source/CMakeLists.txt")" = "${prepared_hash}"
ln -s "${fixture}/source" "${fixture}/source-link"
if bash "${repo_root}/build/release/agent-host/prepare-agent-host.sh" "${fixture}/source-link"; then
    echo "source preparation unexpectedly accepted symlink destination" >&2
    exit 1
fi

# Independent postcondition scan, not a second copy of source preparation.
python3 - "${fixture}/source" <<'PY'
from pathlib import Path
import re
import sys

root = Path(sys.argv[1])
pattern = re.compile(r"(?i)\b(?:https?|git)://[^/\s:@]+:[^/\s@]+@[^\\\"\s]+")
for candidate in root.rglob("*"):
    if candidate.is_file() and pattern.search(candidate.read_text(encoding="utf-8", errors="ignore")):
        raise SystemExit(f"authenticated URL remains in {candidate.relative_to(root)}")
PY

grep -q 'src/services/pixiu_host_compat.cpp' "${fixture}/source/CMakeLists.txt"
grep -q 'add_subdirectory(pixiu/frontend/management)' "${fixture}/source/CMakeLists.txt"
grep -q 'new pixiu::MemoryWorkspace(workspaces)' "${fixture}/source/src/ui/mainwindow.cpp"
test -f "${fixture}/source/pixiu/frontend/management/MemoryWorkspace.cpp"
test ! -e "${fixture}/source/pixiu/frontend/src/main.cpp"
grep -q 'app.setApplicationVersion(QStringLiteral(PIXIU_PRODUCT_VERSION))' "${fixture}/source/src/main.cpp"
grep -q 'PIXIU_PRODUCT_VERSION' "${fixture}/source/CMakeLists.txt"
python3 - "${fixture}/source/src/main.cpp" "${repo_root}" <<'PY'
from pathlib import Path
import sys
source = Path(sys.argv[1]).read_text()
assert 'app.setApplicationDisplayName("PIXIU")' in source, 'product display name is overwritten'
assert 'app.setWindowIcon(QIcon(":/pixiu.svg"))' in source, 'host icon differs from installed product icon'
assert 'window.setWindowTitle("KylinAgent")' not in source, 'startup overrides the product window title'
assert 'app.setApplicationName("KylinAgent")' in source, 'persistent application identity must be preserved'
assert 'app.setOrganizationName("KylinAgent")' in source, 'persistent organization identity must be preserved'
assert 'app.setDesktopFileName("com.kylin.pixiu")' in source, 'host must identify the installed product desktop entry'
desktop = Path(sys.argv[2]) / 'frontend/resources/com.kylin.pixiu.desktop'
assert desktop.is_file(), 'product desktop entry source is missing'
packager = (Path(sys.argv[2]) / 'build/release/scripts/build-deb.sh').read_text()
assert '${STAGE}/usr/share/applications/com.kylin.pixiu.desktop' in packager, 'declared desktop entry is not packaged'
PY
cmp "${repo_root}/VERSION" "${fixture}/source/pixiu/VERSION"
grep -q 'GatewayService gatewayService' "${fixture}/source/src/main.cpp"
grep -q 'app.setQuitOnLastWindowClosed(true)' "${fixture}/source/src/main.cpp"
grep -q 'pixiu::HostCloseGuard closeGuard(&window,' "${fixture}/source/src/main.cpp"
grep -q 'return window.hasPendingAgentRequests();' "${fixture}/source/src/main.cpp"
grep -q 'return window.hasUnsentAgentDraft();' "${fixture}/source/src/main.cpp"
grep -q 'return !m_pendingFallbackReplies.isEmpty();' "${fixture}/source/include/ui/chatwidget.h"
grep -q 'return !m_inputEdit->toPlainText().isEmpty();' "${fixture}/source/src/ui/chatwidget.cpp"
test -f "${fixture}/source/pixiu/frontend/management/HostCloseGuard.cpp"
for close_state_source in HostCloseGuard.cpp HostCloseGuard.h MemoryWorkspace.h DeliveryPage.cpp DeliveryPage.h ServiceStatusPage.cpp ServiceStatusPage.h; do
    cmp "${repo_root}/frontend/management/${close_state_source}" \
        "${fixture}/source/pixiu/frontend/management/${close_state_source}"
done
grep -q 'guard && guard->confirmExit(updateDialog)' "${fixture}/source/pixiu/frontend/management/SettingsWorkspace.cpp"
python3 - "${fixture}/source/src/main.cpp" <<'PY'
from pathlib import Path
import sys

source = Path(sys.argv[1]).read_text()
quit_branch = source.split('message == QStringLiteral("quit")', 1)[1].split('\n        }', 1)[0]
assert quit_branch.index('window.showFromTray();') < quit_branch.index('window.close();')
assert source.count('pixiu::HostCloseGuard closeGuard(&window,') == 1
PY
! grep -q 'setQuitOnLastWindowClosed(false)' "${fixture}/source/src/main.cpp"
! grep -q 'src/ui/modelsettingswidget.cpp' "${fixture}/source/CMakeLists.txt"
grep -q '/v1/chat/completions' "${fixture}/source/src/services/pixiu_host_compat.cpp"
grep -q 'chatCompletionFinished' "${fixture}/source/src/services/pixiu_host_compat.cpp"
grep -q 'event: hermes.tool.progress' "${fixture}/source/src/services/pixiu_host_compat.cpp" || \
    grep -q 'hermes.tool.progress' "${fixture}/source/src/services/pixiu_host_compat.cpp"
grep -q 'emit streamDetailEvent' "${fixture}/source/src/services/pixiu_host_compat.cpp"
grep -q 'emit segmentBoundary' "${fixture}/source/src/services/pixiu_host_compat.cpp"
grep -q 'setWindowTitle(QStringLiteral("PIXIU"))' "${fixture}/source/src/ui/mainwindow.cpp"
cmp "${repo_root}/frontend/resources/icons/pixiu.svg" "${fixture}/source/res/pixiu.svg"
grep -q '<file alias="pixiu.svg">pixiu.svg</file>' "${fixture}/source/res/res.qrc"
grep -q '分布式记忆工作台' "${fixture}/source/src/ui/mainwindow.cpp"
grep -q '选择云端模型' "${fixture}/source/src/ui/chatwidget.cpp"
grep -q '麒灵系统云模型' "${fixture}/source/src/services/modelservice.cpp"
grep -q 'QStringLiteral("kylin-genai")' "${fixture}/source/src/services/modelservice.cpp"
grep -q 'https://api.deepseek.com/v1' "${fixture}/source/src/services/modelservice.cpp"
grep -q 'providerPriority' "${fixture}/source/src/ui/chatwidget.cpp"
grep -q 'QStringLiteral("kylin-genai")' "${fixture}/source/src/ui/chatwidget.cpp"
grep -q 'QStringLiteral("deepseek")' "${fixture}/source/src/ui/chatwidget.cpp"
! grep -q 'ModelProvider(QStringLiteral("ollama")' "${fixture}/source/src/services/modelservice.cpp"
! grep -q 'ModelProvider(QStringLiteral("lmstudio")' "${fixture}/source/src/services/modelservice.cpp"
! grep -q 'ModelProvider(QStringLiteral("openrouter")' "${fixture}/source/src/services/modelservice.cpp"
grep -q 'm_apiKeyEdit->setEchoMode(QLineEdit::Password)' "${fixture}/source/src/ui/modelsettingsdialog.cpp"
grep -q 'credential_configured' "${fixture}/source/src/ui/modelsettingsdialog.cpp"
grep -q 'replaceConfigModelsSync' "${fixture}/source/src/ui/modelsettingsdialog.cpp"
grep -q '/api/config/models' "${fixture}/source/src/services/pixiu_host_compat.cpp"
grep -q 'probeConfigModelSync' "${fixture}/source/src/ui/modelsettingsdialog.cpp"
grep -q '/api/config/models/probe' "${fixture}/source/src/services/pixiu_host_compat.cpp"
grep -q '系统 AI 模块管理' "${fixture}/source/src/ui/modelsettingsdialog.cpp"
grep -q 'messageRole' "${fixture}/source/src/ui/chatwidget.cpp"
grep -q 'class ChatInputEdit final' "${fixture}/source/src/ui/chatwidget.cpp"
grep -q 'ShiftModifier' "${fixture}/source/src/ui/chatwidget.cpp"
grep -q 'ControlModifier' "${fixture}/source/src/ui/chatwidget.cpp"
grep -q '正在思考' "${fixture}/source/src/ui/chatwidget.cpp"
grep -q 'activityCard' "${fixture}/source/src/ui/chatwidget.cpp"
grep -q 'persistCurrentStreamSegment' "${fixture}/source/src/ui/chatwidget.cpp"
grep -q 'ProductThemeV2' "${fixture}/source/src/utils/thememanager.cpp"
grep -q 'QWidget \*rowWidget = new QWidget(m_messagesContainer)' "${fixture}/source/src/ui/chatwidget.cpp"
grep -q 'm_messagesLayout->insertWidget(qMax(0, m_messagesLayout->count() - 1), rowWidget)' "${fixture}/source/src/ui/chatwidget.cpp"
! grep -q 'insertLayout(qMax(0, m_messagesLayout->count() - 1), row)' "${fixture}/source/src/ui/chatwidget.cpp"
grep -q 'delete item->widget()' "${fixture}/source/src/ui/chatwidget.cpp"
grep -q 'composerShell->setMaximumWidth(960)' "${fixture}/source/src/ui/chatwidget.cpp"
grep -q 'messageColumn->setMaximumWidth(920)' "${fixture}/source/src/ui/chatwidget.cpp"
grep -q 'row->addWidget(messageColumn, 20)' "${fixture}/source/src/ui/chatwidget.cpp"
grep -q 'columnLayout->addWidget(messageStack, 1)' "${fixture}/source/src/ui/chatwidget.cpp"
grep -q 'messageAuthor' "${fixture}/source/src/ui/chatwidget.cpp"
grep -q 'QSizePolicy::Expanding, QSizePolicy::Maximum' "${fixture}/source/src/ui/chatwidget.cpp"
grep -q 'horizontalAdvance(content.simplified())' "${fixture}/source/src/ui/chatwidget.cpp"
grep -q 'QTimer::singleShot(0, m_messagesArea' "${fixture}/source/src/ui/chatwidget.cpp"
grep -q '云端模型暂未响应' "${fixture}/source/src/ui/chatwidget.cpp"
grep -q 'legacyFallback' "${fixture}/source/src/ui/chatwidget.cpp"
grep -q 'setHorizontalScrollBarPolicy(Qt::ScrollBarAlwaysOff)' "${fixture}/source/src/ui/sessionlistwidget.cpp"
grep -q 'setTextElideMode(Qt::ElideRight)' "${fixture}/source/src/ui/sessionlistwidget.cpp"
grep -q '#1456b8' "${fixture}/source/src/utils/thememanager.cpp"
grep -q '#69b1ff' "${fixture}/source/src/utils/thememanager.cpp"
grep -q 'themeOption' "${fixture}/source/src/ui/settingsdialog.cpp"
grep -q 'ThemeManager::Light' "${fixture}/source/src/ui/settingsdialog.cpp"
grep -q 'ThemeManager::Dark' "${fixture}/source/src/ui/settingsdialog.cpp"
grep -q '你是 PIXIU' "${fixture}/source/src/services/gatewayservice.cpp"
grep -q '你的记忆体系由 PIXIU 长期记忆和本地会话上下文组成' "${fixture}/source/src/services/gatewayservice.cpp"
grep -q 'updateDefaultSoulMd' "${fixture}/source/src/services/gatewayservice.cpp"
grep -q 'class RichMessageView' "${fixture}/source/src/ui/chatwidget.cpp"
grep -q 'QWebEngineView' "${fixture}/source/src/ui/chatwidget.cpp"
grep -q 'renderMarkdown' "${fixture}/source/src/ui/chatwidget.cpp"
grep -q 'pixiu-wheel:' "${fixture}/source/src/ui/chatwidget.cpp"
grep -q 'contentHeightChanged' "${fixture}/source/src/ui/chatwidget.cpp"
grep -q 'scrollToBottom(true)' "${fixture}/source/src/ui/chatwidget.cpp"
grep -q 'markdown-it.min.js' "${fixture}/source/res/message-renderer/index.html"
grep -q 'markdown-it-texmath.js' "${fixture}/source/res/message-renderer/index.html"
grep -q 'katex.min.js' "${fixture}/source/res/message-renderer/index.html"
grep -q 'mermaid.min.js' "${fixture}/source/res/message-renderer/index.html"
grep -q 'QStringLiteral("tool")' "${fixture}/source/src/ui/chatwidget.cpp"
grep -q 'activityPulse' "${fixture}/source/src/ui/chatwidget.cpp"
grep -q 'activityColumn' "${fixture}/source/src/ui/chatwidget.cpp"
grep -q 'legacyIdentity' "${fixture}/source/src/ui/chatwidget.cpp"
grep -q 'QRegularExpression' "${fixture}/source/src/ui/chatwidget.cpp"
! grep -q 'card, 0, Qt::AlignHCenter' "${fixture}/source/src/ui/chatwidget.cpp"
! grep -q 'Database:' "${fixture}/source/src/ui/mainwindow.cpp"
! grep -q 'setStyleSheet' "${fixture}/source/src/ui/mainwindow.cpp"
! grep -q 'setStyleSheet' "${fixture}/source/src/ui/sidebar.cpp"
! grep -q 'setStyleSheet' "${fixture}/source/src/ui/chatwidget.cpp"
! grep -q 'setStyleSheet' "${fixture}/source/src/ui/sessionlistwidget.cpp"
grep -q -- '--hide' "${repo_root}/build/release/agent-host/build-agent-host.sh"
! grep -q -- 'kylin-agent.*--version' "${repo_root}/build/release/agent-host/build-agent-host.sh"

python3 - "${fixture}/source/src/ui/mainwindow.cpp" <<'PY'
import pathlib
import sys

source = pathlib.Path(sys.argv[1]).read_text()
assert source.count('workspaces->addTab(') == 4
assert 'new pixiu::DevicePage(workspaces)' in source
assert 'new pixiu::SettingsWorkspace(workspaces)' in source
settings = source.split('void MainWindow::openSettings()', 1)[1].split('\n}', 1)[0]
assert 'workspaces->setCurrentIndex(3)' in settings
assert 'dialog.exec()' not in settings
session = source.split('void MainWindow::loadSession(', 1)[1].split('\n}', 1)[0]
assert 'workspaces->setCurrentIndex(0)' in session
PY

echo "agent host adaptation tests: OK"
