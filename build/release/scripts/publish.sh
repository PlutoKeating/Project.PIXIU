#!/usr/bin/env bash
# PIXIU 发布：生成/签名资产清单并拷贝六件套到 dist/<channel>，可选 rsync 远端。
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/functions.sh"

CHANNEL="${1:-staging}"
case "${CHANNEL}" in
    staging|production) ;;
    *) die "channel must be staging or production, got '${CHANNEL}'" ;;
esac

resolve_version
OUT="$(out_dir)"
DIST="$(dist_dir)/${CHANNEL}"
DEB="pixiu_${PIXIU_VERSION}-${PIXIU_REVISION}_${PIXIU_ARCH}.deb"

[ -f "${OUT}/${DEB}" ] || die "build artifact missing: ${OUT}/${DEB}（先执行 build-deb.sh）"
[ -f "${OUT}/${DEB}.sha256.sig" ] || \
    die "signed checksum missing: ${OUT}/${DEB}.sha256.sig（先用离线密钥执行 sign-release.sh）"
MANIFEST="${DEB%.deb}.assets.json"
"${PIXIU_PYTHON:-python3}" \
    "${PIXIU_RELEASE_DIR}/scripts/generate-artifact-manifest.py" \
    --deb "${OUT}/${DEB}" \
    --checksum "${OUT}/${DEB}.sha256" \
    --signature "${OUT}/${DEB}.sha256.sig" \
    --public-key "${PIXIU_RELEASE_DIR}/keys/pixiu-release-ed25519.pub" \
    --channel "${CHANNEL}" \
    --git-commit "$(git -C "${PIXIU_ROOT}" rev-parse HEAD)" \
    --output "${OUT}/${MANIFEST}"
(
    cd "${OUT}"
    sha256sum "${MANIFEST}" > "${MANIFEST}.sha256"
)
"${PIXIU_RELEASE_DIR}/scripts/sign-release.sh" "${OUT}/${MANIFEST}.sha256"
mkdir -p "${DIST}"
cp "${OUT}/${DEB}" "${OUT}/${DEB}.sha256" \
    "${OUT}/${DEB}.sha256.sig" "${OUT}/${MANIFEST}" \
    "${OUT}/${MANIFEST}.sha256" "${OUT}/${MANIFEST}.sha256.sig" "${DIST}/"
{
    printf '%s\t%s\t%s\t%s\n' \
        "$(date -Is)" \
        "${CHANNEL}" \
        "${PIXIU_VERSION}-${PIXIU_REVISION}" \
        "$(git -C "${PIXIU_ROOT}" rev-parse --short HEAD 2>/dev/null || echo unknown)"
} >> "${DIST}/RELEASES.tsv"
log "published ${DEB} -> ${DIST}"

if [ -n "${PIXIU_PUBLISH_URI:-}" ]; then
    command -v rsync >/dev/null 2>&1 || die "PIXIU_PUBLISH_URI set but rsync missing"
    log "rsync -> ${PIXIU_PUBLISH_URI}/${CHANNEL}/"
    rsync -av "${DIST}/" "${PIXIU_PUBLISH_URI}/${CHANNEL}/"
fi
