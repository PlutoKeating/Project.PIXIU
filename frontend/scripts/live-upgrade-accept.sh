#!/usr/bin/env bash
# 本机应用内升级验收：真实 GitHub latest + CheckUpdateDialog + install-update。
# 已安装版本若等于 latest，测试把 applicationVersion 压到 0.1.5 以走完整安装链。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BUILD="${PIXIU_LIVE_BUILD:-${ROOT}/frontend/build-live-upgrade}"
SNAP="${PIXIU_LIVE_SNAP:-/tmp/pixiu-upgrade-accept}"
mkdir -p "${SNAP}"

sudo sha256sum /etc/pixiu/pixiu.env | tee "${SNAP}/env.before"
sudo python3 - <<'PY' | tee "${SNAP}/device.before"
import sqlite3
c = sqlite3.connect("/var/lib/pixiu/pixiu.db")
print(c.execute("select device_id from sync_identity").fetchone()[0])
PY
curl -fsS -o "${SNAP}/openapi.before.json" http://127.0.0.1:8765/openapi.json

cmake -S "${ROOT}/frontend" -B "${BUILD}" \
    -DPIXIU_HAVE_KYSDK=OFF -DCMAKE_BUILD_TYPE=Release
cmake --build "${BUILD}" --target t_upgrade_live -j"$(nproc)"

export PIXIU_LIVE_UPGRADE=1
export PIXIU_LIVE_UPGRADE_INSTALL="${PIXIU_LIVE_UPGRADE_INSTALL:-1}"
# 使用真实会话 DISPLAY，让对话框实际绘制；不要 offscreen。
unset QT_QPA_PLATFORM || true

"${BUILD}/t_upgrade_live"

sudo sha256sum /etc/pixiu/pixiu.env | tee "${SNAP}/env.after"
sudo python3 - <<'PY' | tee "${SNAP}/device.after"
import sqlite3
c = sqlite3.connect("/var/lib/pixiu/pixiu.db")
print(c.execute("select device_id from sync_identity").fetchone()[0])
PY
curl -fsS -o "${SNAP}/openapi.after.json" http://127.0.0.1:8765/openapi.json
dpkg-query -W -f='${Package} ${Version} ${Status}\n' pixiu
systemctl is-active pixiu-backend.service

cmp "${SNAP}/env.before" "${SNAP}/env.after"
cmp "${SNAP}/device.before" "${SNAP}/device.after"
echo "live upgrade accept: config and device identity unchanged"
