#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
GENERATOR="${ROOT}/build/release/scripts/generate-release-manifest.py"
TMP="$(mktemp -d)"
cleanup() {
    rm -f -- "${DIRTY_MARKER:-}"
    rm -rf -- "${TMP}"
}
trap cleanup EXIT
MANIFEST="${TMP}/release-manifest.json"
PRODUCT_VERSION="$(tr -d '\r\n' < "${ROOT}/VERSION")"
IFS=. read -r VERSION_MAJOR VERSION_MINOR VERSION_PATCH <<EOF
${PRODUCT_VERSION}
EOF
MISMATCH_VERSION="${VERSION_MAJOR}.${VERSION_MINOR}.$((10#${VERSION_PATCH} + 1))"

PIXIU_VERSION="${PRODUCT_VERSION}" \
PIXIU_REVISION=9 \
PIXIU_ARCH=amd64 \
PIXIU_PROFILE=manifest-test \
PIXIU_KYSDK=OFF \
PIXIU_INSTALL_STRICT=0 \
PIXIU_PYTHON_VERSION=312 \
SOURCE_DATE_EPOCH=0 \
    python3 "${GENERATOR}" --root "${ROOT}" --output "${MANIFEST}"

python3 - "${ROOT}" "${MANIFEST}" "${PRODUCT_VERSION}" <<'PY'
import json
import subprocess
import sys
from pathlib import Path

root = Path(sys.argv[1])
manifest = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
product_version = sys.argv[3]

assert manifest["manifest_schema"] == 1
assert manifest["product"] == {
    "name": "pixiu",
    "version": product_version,
    "revision": "9",
    "debian_version": f"{product_version}-9",
}
assert manifest["build"]["architecture"] == "amd64"
assert manifest["build"]["profile"] == "manifest-test"
assert manifest["build"]["kysdk"] == "OFF"
assert manifest["build"]["install_strict"] is False
assert manifest["build"]["python_abi"] == "312"
assert manifest["build"]["built_at_utc"] == "1970-01-01T00:00:00Z"
assert manifest["build"]["git_commit"] == subprocess.check_output(
    ["git", "-C", str(root), "rev-parse", "HEAD"], text=True
).strip()

assert manifest["interfaces"] == {
    "http_api": "0.2.0",
    "agent_memory_api": 1,
    "database_schema": 12,
}
assert manifest["provider"] == {"name": "pixiu", "version": product_version}
assert manifest["host_compatibility"]["agent_runtime"]["supported"] == "0.9.x"
assert manifest["host_compatibility"]["agent_runtime"]["declared_versions"] == {
    "package_metadata": "0.9.8",
    "version_file": "0.9.9",
}
assert manifest["host_compatibility"]["kylin_agent"]["declared_version"] == "0.9.6"
assert manifest["host_compatibility"]["kylin_agent"]["license"] == {
    "family": "GNU Affero General Public License v3",
    "spdx_expression": None,
    "review_status": "pending-only-or-later-review",
}
assert manifest["sdk_sources"]["embedding"]["license"]["spdx_expression"] == (
    "GPL-3.0-or-later"
)

for name, path in {
    "kylin_agent": "third_party/kylin-agent",
    "agent_runtime": "third_party/kylin-agent-runtime",
    "embedding": "third_party/kylin-coreai-embedding",
    "vector_engine": "third_party/libkysdk-vector-engine-client",
}.items():
    group = "host_compatibility" if name in {"kylin_agent", "agent_runtime"} else "sdk_sources"
    expected = subprocess.check_output(
        ["git", "-C", str(root), "rev-parse", f"HEAD:{path}"], text=True
    ).strip()
    assert manifest[group][name]["source_commit"] == expected
    assert manifest[group][name]["gitlink_commit"] == expected
    assert manifest[group][name]["source_tree_clean"] is True
PY

if PIXIU_VERSION="${MISMATCH_VERSION}" \
        PIXIU_REVISION=1 \
        PIXIU_ARCH=amd64 \
        PIXIU_PROFILE=manifest-test \
        PIXIU_KYSDK=OFF \
        PIXIU_INSTALL_STRICT=0 \
        PIXIU_PYTHON_VERSION=312 \
        python3 "${GENERATOR}" --root "${ROOT}" \
            --output "${TMP}/mismatched.json" >/dev/null 2>&1; then
    echo "release manifest must reject product-version drift" >&2
    exit 1
fi

DIRTY_MARKER="${ROOT}/third_party/kylin-agent/.pixiu-manifest-dirty-test"
touch "${DIRTY_MARKER}"
if PIXIU_VERSION="${PRODUCT_VERSION}" \
        PIXIU_REVISION=1 \
        PIXIU_ARCH=amd64 \
        PIXIU_PROFILE=manifest-test \
        PIXIU_KYSDK=OFF \
        PIXIU_INSTALL_STRICT=0 \
        PIXIU_PYTHON_VERSION=312 \
        python3 "${GENERATOR}" --root "${ROOT}" \
            --output "${TMP}/dirty-submodule.json" >/dev/null 2>&1; then
    rm -f -- "${DIRTY_MARKER}"
    echo "release manifest must reject dirty submodule checkouts" >&2
    exit 1
fi
rm -f -- "${DIRTY_MARKER}"

grep -q 'release-manifest.json' "${ROOT}/build/release/scripts/build-deb.sh"
grep -q 'Verify package component manifest' "${ROOT}/.github/workflows/ci.yml"
grep -q 'release-manifest.json' "${ROOT}/.github/workflows/release.yml"

printf 'release manifest tests: OK\n'
