#!/usr/bin/env bash
# Rehearse the two-release Ed25519 trust-anchor rotation without production keys.
set -euo pipefail

TMP="$(mktemp -d)"
trap 'rm -rf -- "${TMP}"' EXIT

OLD_PRIVATE="${TMP}/old-private.pem"
OLD_PUBLIC="${TMP}/old-public.pem"
NEW_PRIVATE="${TMP}/new-private.pem"
NEW_PUBLIC="${TMP}/new-public.pem"
TRUSTED_PUBLIC="${TMP}/trusted-release-key.pem"

openssl genpkey -algorithm ED25519 -out "${OLD_PRIVATE}" >/dev/null 2>&1
openssl pkey -in "${OLD_PRIVATE}" -pubout -out "${OLD_PUBLIC}"
openssl genpkey -algorithm ED25519 -out "${NEW_PRIVATE}" >/dev/null 2>&1
openssl pkey -in "${NEW_PRIVATE}" -pubout -out "${NEW_PUBLIC}"
chmod 0600 "${OLD_PRIVATE}" "${NEW_PRIVATE}"
cp "${OLD_PUBLIC}" "${TRUSTED_PUBLIC}"

canonical_digest() {
    local artifact="$1"
    local output="$2"
    sha256sum "${artifact}" | awk '{print tolower($1)}' >"${output}"
}

sign_digest() {
    local digest="$1"
    local private_key="$2"
    local signature="$3"
    openssl pkeyutl -sign -rawin -in "${digest}" \
        -inkey "${private_key}" -out "${signature}"
}

verify_digest() {
    local digest="$1"
    local public_key="$2"
    local signature="$3"
    openssl pkeyutl -verify -pubin -rawin -in "${digest}" \
        -inkey "${public_key}" -sigfile "${signature}" >/dev/null 2>&1
}

build_fixture_package() {
    local root="$1"
    local version="$2"
    local output="$3"
    mkdir -p "${root}/DEBIAN"
    printf '%s\n' \
        'Package: pixiu' \
        "Version: ${version}" \
        'Architecture: all' \
        'Maintainer: PIXIU Rotation Test <test@pixiu.invalid>' \
        'Description: Ephemeral release-key rotation fixture' \
        >"${root}/DEBIAN/control"
    dpkg-deb --build --root-owner-group "${root}" "${output}" >/dev/null
}

# Release N is accepted with the old trust anchor and carries the next anchor.
mkdir -p "${TMP}/transition/usr/share/pixiu/keys"
cp "${NEW_PUBLIC}" \
    "${TMP}/transition/usr/share/pixiu/keys/pixiu-release-ed25519.pub"
build_fixture_package "${TMP}/transition" 1.0.0-1 \
    "${TMP}/pixiu-transition.deb"
canonical_digest "${TMP}/pixiu-transition.deb" "${TMP}/transition.digest"
sign_digest "${TMP}/transition.digest" "${OLD_PRIVATE}" \
    "${TMP}/transition.sig"
verify_digest "${TMP}/transition.digest" "${TRUSTED_PUBLIC}" \
    "${TMP}/transition.sig"

# Installing the authenticated transition release changes only the public anchor.
mkdir "${TMP}/installed-transition"
dpkg-deb --extract "${TMP}/pixiu-transition.deb" \
    "${TMP}/installed-transition"
install -m 0644 \
    "${TMP}/installed-transition/usr/share/pixiu/keys/pixiu-release-ed25519.pub" \
    "${TRUSTED_PUBLIC}"
cmp -s "${TRUSTED_PUBLIC}" "${NEW_PUBLIC}"

# Release N+1 is signed by the new key. The new anchor accepts it and the old
# anchor does not, proving the exercise really crossed the trust boundary.
mkdir -p "${TMP}/post-rotation/usr/share/pixiu"
printf 'release=post-rotation\n' >"${TMP}/post-rotation/usr/share/pixiu/version"
build_fixture_package "${TMP}/post-rotation" 1.1.0-1 \
    "${TMP}/pixiu-post-rotation.deb"
canonical_digest "${TMP}/pixiu-post-rotation.deb" "${TMP}/post-rotation.digest"
sign_digest "${TMP}/post-rotation.digest" "${NEW_PRIVATE}" \
    "${TMP}/post-rotation.sig"
verify_digest "${TMP}/post-rotation.digest" "${TRUSTED_PUBLIC}" \
    "${TMP}/post-rotation.sig"
if verify_digest "${TMP}/post-rotation.digest" "${OLD_PUBLIC}" \
        "${TMP}/post-rotation.sig"; then
    echo "rotation test: old trust anchor accepted the new-key release" >&2
    exit 1
fi

printf 'release key rotation tests: OK\n'
