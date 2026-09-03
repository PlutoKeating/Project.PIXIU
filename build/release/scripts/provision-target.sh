#!/usr/bin/env bash
# 目标机运行依赖预置（幂等）：在全新麒麟/Ubuntu 上安装 .deb 所需的系统包。
# 用法：sudo bash provision-target.sh [profile] [--with-test-deps] [--with-build-deps]
set -euo pipefail

PROFILE="${1:-kylin-v11-x86_64}"
WITH_TEST_DEPS=0
WITH_BUILD_DEPS=0
for option in "${@:2}"; do
    case "${option}" in
        --with-test-deps) WITH_TEST_DEPS=1 ;;
        --with-build-deps) WITH_BUILD_DEPS=1 ;;
        *) echo "unknown option: ${option}" >&2; exit 2 ;;
    esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [ -n "${PIXIU_PROFILE_FILE:-}" ] && [ -f "${PIXIU_PROFILE_FILE}" ]; then
    PROFILE_FILE="${PIXIU_PROFILE_FILE}"
else
    PROFILE_FILE="${SCRIPT_DIR}/../profiles/${PROFILE}.env"
fi
[ -f "${PROFILE_FILE}" ] || { echo "profile not found: ${PROFILE_FILE}" >&2; exit 1; }
# shellcheck source=/dev/null
. "${PROFILE_FILE}"

command -v apt-get >/dev/null 2>&1 || { echo "apt-get required" >&2; exit 1; }

export DEBIAN_FRONTEND=noninteractive
echo "[pixiu-provision] apt update"
apt-get update -qq
echo "[pixiu-provision] installing runtime deps: ${APT_RUNTIME_DEPS}"
apt-get install -y -qq ${APT_RUNTIME_DEPS}

# python3-pip / python3-venv 若发行版提供则一并安装（缺失时由 deb postinst 自举）
apt-get install -y -qq python3-pip python3-venv 2>/dev/null || \
    echo "[pixiu-provision] python3-pip/python3-venv 不在本发行版源中（由 deb postinst 自举）"

if [ "${WITH_TEST_DEPS}" = "1" ] && [ -n "${APT_TEST_DEPS:-}" ]; then
    echo "[pixiu-provision] installing test deps: ${APT_TEST_DEPS}"
    apt-get install -y -qq ${APT_TEST_DEPS}
fi
if [ "${WITH_BUILD_DEPS}" = "1" ] && [ -n "${APT_BUILD_DEPS:-}" ]; then
    echo "[pixiu-provision] installing build deps: ${APT_BUILD_DEPS}"
    apt-get install -y -qq ${APT_BUILD_DEPS}
fi
echo "[pixiu-provision] done"
