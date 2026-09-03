#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
GENERATOR="${ROOT}/build/release/scripts/generate-artifact-manifest.py"
TMP="$(mktemp -d)"
trap 'rm -rf -- "${TMP}"' EXIT
PRODUCT_VERSION="$(tr -d '\r\n' < "${ROOT}/VERSION")"
DEB="${TMP}/pixiu_${PRODUCT_VERSION}-7_amd64.deb"
CHECKSUM="${DEB}.sha256"
SIGNATURE="${CHECKSUM}.sig"
MANIFEST="${TMP}/pixiu_${PRODUCT_VERSION}-7_amd64.assets.json"
PRIVATE_KEY="${TMP}/private.pem"
PUBLIC_KEY="${TMP}/public.pem"
GIT_COMMIT="$(git -C "${ROOT}" rev-parse HEAD)"

mkdir -p "${TMP}/package/DEBIAN" "${TMP}/package/usr/share/pixiu"
printf '%s\n' \
    'Package: pixiu' "Version: ${PRODUCT_VERSION}-7" 'Architecture: amd64' \
    'Maintainer: PIXIU Test <test@example.invalid>' \
    'Description: PIXIU asset manifest test' > "${TMP}/package/DEBIAN/control"
printf '{"product":{"debian_version":"%s-7"},"build":{"architecture":"amd64","git_commit":"%s"}}\n' \
    "${PRODUCT_VERSION}" "${GIT_COMMIT}" \
    > "${TMP}/package/usr/share/pixiu/release-manifest.json"
dpkg-deb --build --root-owner-group "${TMP}/package" "${DEB}" >/dev/null
(cd "${TMP}" && sha256sum "$(basename "${DEB}")" > "$(basename "${CHECKSUM}")")
openssl genpkey -algorithm Ed25519 -out "${PRIVATE_KEY}" >/dev/null 2>&1
openssl pkey -in "${PRIVATE_KEY}" -pubout -out "${PUBLIC_KEY}" >/dev/null 2>&1
awk '{print tolower($1)}' "${CHECKSUM}" > "${TMP}/digest"
openssl pkeyutl -sign -rawin -in "${TMP}/digest" \
    -inkey "${PRIVATE_KEY}" -out "${SIGNATURE}"

SOURCE_DATE_EPOCH=0 python3 "${GENERATOR}" \
    --deb "${DEB}" --checksum "${CHECKSUM}" --signature "${SIGNATURE}" \
    --public-key "${PUBLIC_KEY}" \
    --channel staging \
    --output "${MANIFEST}"

python3 - "${MANIFEST}" "${PRODUCT_VERSION}" "${GIT_COMMIT}" <<'PY'
import hashlib
import json
import sys
from pathlib import Path

path = Path(sys.argv[1])
version = sys.argv[2]
git_commit = sys.argv[3]
manifest = json.loads(path.read_text(encoding="utf-8"))
assert manifest["manifest_schema"] == 1
assert manifest["product_version"] == version
assert manifest["debian_version"] == f"{version}-7"
assert manifest["architecture"] == "amd64"
assert manifest["channel"] == "staging"
assert manifest["generated_at_utc"] == "1970-01-01T00:00:00Z"
assert manifest["git_commit"] == git_commit
assert [asset["role"] for asset in manifest["assets"]] == [
    "package", "checksum", "signature"
]
for asset in manifest["assets"]:
    source = path.parent / asset["name"]
    assert asset["size_bytes"] == source.stat().st_size
    assert asset["sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()
assert manifest["authentication"] == {
    "checksum": f"{path.name}.sha256",
    "signature": f"{path.name}.sha256.sig",
    "algorithm": "Ed25519-over-lowercase-SHA256",
}
assert manifest["generation"]["tool"].endswith("generate-artifact-manifest.py")
assert "--git-commit" not in manifest["generation"]["command"]
PY

if python3 "${GENERATOR}" \
        --deb "${DEB}" --checksum "${CHECKSUM}" --signature "${SIGNATURE}" \
        --public-key "${PUBLIC_KEY}" --channel staging \
        --output "${DEB}" >/dev/null 2>&1; then
    echo "artifact manifest must not overwrite an input asset" >&2
    exit 1
fi

cp "${SIGNATURE}" "${TMP}/signature.good"
printf 'x' >> "${SIGNATURE}"
if python3 "${GENERATOR}" \
        --deb "${DEB}" --checksum "${CHECKSUM}" --signature "${SIGNATURE}" \
        --public-key "${PUBLIC_KEY}" \
        --channel staging \
        --output "${TMP}/bad-signature.json" >/dev/null 2>&1; then
    echo "artifact manifest must reject an invalid release signature" >&2
    exit 1
fi
mv "${TMP}/signature.good" "${SIGNATURE}"

printf 'tampered\n' >> "${DEB}"
if python3 "${GENERATOR}" \
        --deb "${DEB}" --checksum "${CHECKSUM}" --signature "${SIGNATURE}" \
        --public-key "${PUBLIC_KEY}" \
        --channel staging \
        --output "${TMP}/tampered.json" >/dev/null 2>&1; then
    echo "artifact manifest must reject a checksum mismatch" >&2
    exit 1
fi

grep -q 'generate-artifact-manifest.py' "${ROOT}/build/release/scripts/publish.sh"
grep -q 'generate-artifact-manifest.py' "${ROOT}/.github/workflows/release.yml"
grep -q '\*.assets.json.sha256.sig' "${ROOT}/.github/workflows/release.yml"

printf 'artifact manifest tests: OK\n'
