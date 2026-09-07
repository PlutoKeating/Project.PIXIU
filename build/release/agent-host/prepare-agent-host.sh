#!/usr/bin/env bash
# Prepare exactly the source tree used by the product build and adaptation tests.
set -euo pipefail

script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
repo_root="$(cd "${script_dir}/../../.." && pwd)"
source_dir="${repo_root}/third_party/kylin-agent"
if [[ "$#" != 1 || ! -d "$1" || -L "$1" ]]; then
    echo "Usage: bash prepare-agent-host.sh <existing empty source directory>" >&2
    exit 2
fi
target_source="$(cd "$1" && pwd -P)"
shopt -s nullglob dotglob
existing_entries=("${target_source}"/*)
if (( ${#existing_entries[@]} != 0 )); then
    echo "Agent source destination must be empty; no files were changed" >&2
    exit 2
fi
shopt -u nullglob dotglob

expected_commit="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1]))["components"]["kylin_agent"]["source_commit"])' "${repo_root}/build/release/agent-supply-chain-policy.json")"

actual_commit="$(git -C "${source_dir}" rev-parse HEAD)"
if [[ "${actual_commit}" != "${expected_commit}" ]]; then
    echo "Agent host commit mismatch: expected ${expected_commit}, got ${actual_commit}" >&2
    exit 2
fi
if [[ -n "$(git -C "${source_dir}" status --porcelain)" ]]; then
    echo "Agent host submodule must be clean" >&2
    exit 2
fi

git -C "${source_dir}" archive --format=tar HEAD | tar -xf - -C "${target_source}"
patch -d "${target_source}" -p1 --forward --batch \
    < "${script_dir}/patches/0001-build-coherent-offline-host.patch"
patch -d "${target_source}" -p1 --forward --batch \
    < "${script_dir}/patches/0002-pixiu-premium-accessible-ui.patch"
patch -d "${target_source}" -p1 --forward --batch \
    < "${script_dir}/patches/0003-kylin-cloud-model-settings.patch"
patch -d "${target_source}" -p1 --forward --batch \
    < "${script_dir}/patches/0004-working-agent-experience.patch"
patch -d "${target_source}" -p1 --forward --batch \
    < "${script_dir}/patches/0005-blue-theme-settings-and-pixiu-soul.patch"
patch -d "${target_source}" -p1 --forward --batch \
    < "${script_dir}/patches/0006-rich-message-rendering.patch"
patch -d "${target_source}" -p1 --forward --batch --no-backup-if-mismatch \
    < "${script_dir}/patches/0007-chat-layout-follow.patch"
patch -d "${target_source}" -p1 --forward --batch --no-backup-if-mismatch \
    < "${script_dir}/patches/0008-pixiu-assistant-history.patch"
patch -d "${target_source}" -p1 --forward --batch --no-backup-if-mismatch \
    < "${script_dir}/patches/0009-optional-kylin-desktop.patch"
patch -d "${target_source}" -p1 --forward --batch --no-backup-if-mismatch \
    --fuzz=0 < "${script_dir}/patches/0010-embedded-memory-workspace.patch"
patch -d "${target_source}" -p1 --forward --batch --fuzz=0 --no-backup-if-mismatch \
    < "${script_dir}/patches/0011-product-application-version.patch"
patch -d "${target_source}" -p1 --forward --batch --fuzz=0 --no-backup-if-mismatch \
    < "${script_dir}/patches/0012-unified-workspace-navigation.patch"
patch -d "${target_source}" -p1 --forward --batch --fuzz=0 --no-backup-if-mismatch \
    < "${script_dir}/patches/0013-close-last-window-exits-host.patch"
for relative in management/CMakeLists.txt management/MemoryWorkspace.h management/MemoryWorkspace.cpp \
    management/MemoryWriteDialog.h management/MemoryWriteDialog.cpp \
    management/MemoryEditDialog.h management/MemoryEditDialog.cpp \
    management/MemoryAudit.h management/MemoryAudit.cpp \
    management/PrivacyPage.h management/PrivacyPage.cpp \
    management/DevicePage.h management/DevicePage.cpp \
    management/PairingDialog.h management/PairingDialog.cpp \
    management/DeliveryPage.h management/DeliveryPage.cpp \
    management/ForgetPage.h management/ForgetPage.cpp \
    management/SettingsWorkspace.h management/SettingsWorkspace.cpp \
    src/app/UpgradeController.h src/app/UpgradeController.cpp src/app/UpgradeUtils.h src/app/UpgradeUtils.cpp \
    src/widgets/CheckUpdateDialog.h src/widgets/CheckUpdateDialog.cpp src/app/UiTokens.h \
    src/services/BackendTransport.h src/services/BackendTransport.cpp \
    src/services/HttpBackendTransport.h src/services/HttpBackendTransport.cpp src/services/BackendTypes.h; do
    install -D -m 0644 "${repo_root}/frontend/${relative}" "${target_source}/pixiu/frontend/${relative}"
done
install -D -m 0644 "${repo_root}/VERSION" "${target_source}/pixiu/VERSION"
install -D -m 0644 "${script_dir}/compat/pixiu_desktop.h" \
    "${target_source}/include/utils/pixiu_desktop.h"
cp -a "${repo_root}/integrations/kylin_agent/message_renderer" \
    "${target_source}/res/message-renderer"
install -D -m 0644 "${script_dir}/compat/pixiu_host_compat.cpp" \
    "${target_source}/src/services/pixiu_host_compat.cpp"
# The public upstream tree contains one credential-bearing clone URL and two
# unused online bootstrap scripts.  They are not admissible in a distributable
# source archive.  Replace exactly that URL with its public upstream and remove
# only the two uncompiled bootstrap files; fail if upstream shape changes.
python3 - "${target_source}" <<'PY'
from pathlib import Path
import re
import sys

root = Path(sys.argv[1])
gateway = root / "src/services/gatewayservice.cpp"
content = gateway.read_text(encoding="utf-8")
pattern = re.compile(r"(?i)\b(?:https?|git)://[^/\s:@]+:[^/\s@]+@[^\\\"\s]+")
content, count = pattern.subn("https://gitee.com/openkylin/kylin-cua.git", content)
if count != 1:
    raise SystemExit(f"expected one authenticated upstream URL, found {count}")
gateway.write_text(content, encoding="utf-8")
for relative in ("scripts/agent_runtime_install.sh", "scripts/agent_runtime_install_bak.sh"):
    candidate = root / relative
    if not candidate.is_file():
        raise SystemExit(f"expected upstream bootstrap file is missing: {relative}")
    candidate.unlink()
PY
