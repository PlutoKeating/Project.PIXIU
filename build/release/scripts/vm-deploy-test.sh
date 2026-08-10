#!/usr/bin/env bash
# 麒麟测试 VM 部署 + 冒烟测试（可重复执行）：
#   构建 .deb（按 PIXIU_PROFILE）→ 上传 → 目标机预置依赖 → dpkg 安装
#   → systemd 服务 → HTTP 端点冒烟 → 前端离屏冒烟 → 可选截图工具
#
# 环境变量：
#   PIXIU_VM_HOST         必填（测试机 IP/域名）
#   PIXIU_VM_USER         默认 pluto（免密密钥登录）
#   PIXIU_PROFILE         默认 kylin-v11-x86_64
#   PIXIU_VM_TEST_DEPS    1 时在目标机安装截图等测试依赖
#   PIXIU_VM_FORCE_REINSTALL  1 时先 dpkg -r 并清空 /usr/lib/pixiu（模拟全新安装）
#   PIXIU_VM_RUN_BACKEND_TESTS 1 时在 VM 上经 github-personal 克隆源码并跑后端 pytest
set -euo pipefail
source "$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/functions.sh"

HOST="${PIXIU_VM_HOST:?PIXIU_VM_HOST must be set}"
VM_USER="${PIXIU_VM_USER:-pluto}"
PROFILE="${PIXIU_PROFILE:-kylin-v11-x86_64}"
WITH_TEST_DEPS="${PIXIU_VM_TEST_DEPS:-0}"
RUN_BACKEND_TESTS="${PIXIU_VM_RUN_BACKEND_TESTS:-0}"

resolve_version
DEB="pixiu_${PIXIU_VERSION}-${PIXIU_REVISION}_${PIXIU_ARCH}.deb"
DEB_PATH="$(out_dir)/${DEB}"
SSH=(ssh -o BatchMode=yes -o ConnectTimeout=10 "${VM_USER}@${HOST}")
SCP=(scp -q -o BatchMode=yes)

# 1) 确保 deb 已构建（构建时按 profile 打包 wheels）
if [ ! -f "${DEB_PATH}" ]; then
    log "deb 不存在，先构建（profile=${PROFILE}）"
    PIXIU_PROFILE="${PROFILE}" bash "${PIXIU_RELEASE_DIR}/scripts/build-deb.sh"
fi

# 2) 上传
log "[1/5] upload deb + provision script"
"${SCP[@]}" "${DEB_PATH}" "${VM_USER}@${HOST}:/tmp/${DEB}"
"${SCP[@]}" "${PIXIU_RELEASE_DIR}/scripts/provision-target.sh" \
    "${VM_USER}@${HOST}:/tmp/pixiu-provision-target.sh"
"${SCP[@]}" "${PIXIU_RELEASE_DIR}/profiles/${PROFILE}.env" \
    "${VM_USER}@${HOST}:/tmp/pixiu-profile.env"

# 3) 预置依赖 + 安装
#    使用 apt-get install ./deb：自动等待 dpkg 锁（系统后台 apt 会占锁）并解析依赖；
#    dpkg -i 无锁等待，实测会因 apt-daily 等后台任务直接失败，因此不作为首选。
log "[2/5] provision + install on ${HOST}"
TEST_DEPS_ARG=""
[ "${WITH_TEST_DEPS}" = "1" ] && TEST_DEPS_ARG="--with-test-deps"
FORCE_REINSTALL=""
if [ "${PIXIU_VM_FORCE_REINSTALL:-0}" = "1" ]; then
    FORCE_REINSTALL="sudo apt-get remove -y pixiu >/dev/null 2>&1 || true; \
sudo rm -rf /usr/lib/pixiu /var/lib/pixiu;"
    log "force reinstall: 先移除旧包与 /usr/lib/pixiu"
fi
"${SSH[@]}" "sudo PIXIU_PROFILE_FILE=/tmp/pixiu-profile.env \
    bash /tmp/pixiu-provision-target.sh ${PROFILE} ${TEST_DEPS_ARG} && \
    ${FORCE_REINSTALL} \
    sudo DEBIAN_FRONTEND=noninteractive apt-get install -y -qq /tmp/${DEB} || \
    { echo '--- install error ---'; exit 1; }"

# 4) 服务与后端冒烟
log "[3/5] backend smoke"
"${SSH[@]}" '
set -u
sudo systemctl enable pixiu-backend.service >/dev/null 2>&1 || true
sudo systemctl restart pixiu-backend.service
echo "--- waiting for HTTP 127.0.0.1:8765 ---"
READY=0
for i in 1 2 3 4 5 6 7 8 9 10; do
    if curl -sf -o /dev/null http://127.0.0.1:8765/conflicts 2>/dev/null; then
        echo "backend HTTP ready after ${i} checks"
        READY=1
        break
    fi
    sleep 2
done
if [ "${READY}" != "1" ]; then
    echo "backend HTTP NOT reachable on 8765"
    sudo systemctl status pixiu-backend.service --no-pager -l | head -10
    sudo journalctl -u pixiu-backend.service -n 30 --no-pager | tail -30
    exit 1
fi
echo "--- service ---"
systemctl is-active pixiu-backend.service
echo "--- db ---"
ls -la /var/lib/pixiu/pixiu.db 2>/dev/null || echo "DB not yet created"
echo "--- GET /conflicts ---"
curl -sS -w "\nHTTP %{http_code}\n" http://127.0.0.1:8765/conflicts
echo "--- GET /sync/status ---"
curl -sS -w "\nHTTP %{http_code}\n" http://127.0.0.1:8765/sync/status
echo "--- POST /memory/write (预期 500：KylinSDK 绑定未构建，见 README 边界) ---"
curl -sS -w "\nHTTP %{http_code}\n" -X POST http://127.0.0.1:8765/memory/write \
    -H "Content-Type: application/json" \
    -d "{\"source_type\":\"MANUAL_CONFIG\",\"raw\":{\"title\":\"t\",\"body\":{\"key\":\"k\",\"enabled\":true}},\"scope\":\"user:test\"}"
echo "--- journal tail ---"
sudo journalctl -u pixiu-backend.service -n 6 --no-pager 2>/dev/null | tail -6
'

# 4) 后端全量测试（可选；经 github-personal 别名克隆私有仓库）
if [ "${RUN_BACKEND_TESTS}" = "1" ]; then
    log "[4/6] backend pytest on VM（github-personal 克隆）"
    "${SSH[@]}" '
        set -e
        SRC=/tmp/pixiu-src
        if [ ! -d "${SRC}/.git" ]; then
            rm -rf "${SRC}"
            git clone -q git@github-personal:PlutoKeating/Project.PIXIU.git "${SRC}"
        else
            git -C "${SRC}" fetch -q origin
            git -C "${SRC}" checkout -q origin/main
        fi
        cd "${SRC}"
        sudo /usr/lib/pixiu/venv/bin/python -m pytest \
            backend/foundation/tests backend/engine/tests \
            -q -p no:cacheprovider
    '
fi

# 5) 前端离屏冒烟
log "[5/6] frontend offscreen smoke"
"${SSH[@]}" '
set +e
timeout 6 env QT_QPA_PLATFORM=offscreen /usr/bin/pixiu-frontend >/tmp/pixiu-front-smoke.log 2>&1
rc=$?
echo "frontend exit: $rc (124=timeout ok)"
tail -4 /tmp/pixiu-front-smoke.log
[ $rc -eq 124 ] || { echo "frontend crashed (rc=$rc)"; exit 1; }
'

log "[6/6] VM deploy+smoke done: ${HOST} / ${DEB}"
