#!/usr/bin/env bash
#
# 真实 UKUI 桌面「快捷入口首击」回归检查（2026-08-10 焦点问题固化）。
#
# 背景：聊天主窗口处于「未激活」状态时，用户第一次直接点击输入区上方的
# 快捷 chip（记忆/设置/录入/同步）必须立即打开对应窗口；不允许首击被当作
# “仅激活/聚焦主窗口”的点击而吞掉（曾观察到首击失效、次击才生效）。
#
# 本脚本把当时手动的 xdotool 实验步骤固化为可复现检查：
#   1) 唤起聊天窗并确认可见
#   2) 打开一个“焦点目标”窗口并点击它，让聊天窗失去激活
#   3) 逐个 chip 只点击一次，判定对应目标窗口是否出现
#
# 前提（务必先满足，否则结果无意义）：
#   - 已在真实 UKUI 桌面会话中运行（DISPLAY 默认 :0，XWayland 逻辑坐标）
#   - pixiu-frontend 已启动，且 scripts/demo_stub_server.py 运行中
#     （后端在线，否则“录入”chip 会因离线被禁用、无法验证）
#   - 界面为默认中文（按窗口标题“记忆管理/设置/录入记忆”判定）
#
# 用法：
#   scripts/desktop_first_click_check.sh
#   DISPLAY=:0 scripts/desktop_first_click_check.sh
#
# 输出：每个入口 PASS/FAIL；任一 FAIL 则退出码非 0。

set -euo pipefail

DISPLAY="${DISPLAY:-:0}"
export DISPLAY

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# 聊天窗内 chip 的窗口相对点击位置（真实桌面插桩验证中校准：
# 380x640 聊天窗 chip 行中心 y≈488，x 依次为记忆/设置/录入/同步）。
CHIP_MEMORY_X=48
CHIP_SETTINGS_X=110
CHIP_IMPORT_X=180
CHIP_SYNC_X=250
CHIP_Y=488

pass_count=0
fail_count=0

log() { printf '[desktop-first-click] %s\n' "$*"; }

win_visible() {
    # 参数为窗口标题正则；任一匹配且已 map 的窗口即视为可见。
    local ids id
    ids="$(xdotool search --name "$1" 2>/dev/null || true)"
    if [[ -z "${ids}" ]]; then
        return 1
    fi
    for id in ${ids}; do
        if xwininfo -id "${id}" 2>/dev/null | grep -q "Map State: IsViewable"; then
            return 0
        fi
    done
    return 1
}

chat_win() {
    # 输出 380x640 聊天窗的窗口 id（PIXIU 中宽度>100 的窗口即聊天窗）。
    local id width
    for id in $(xdotool search --name "^PIXIU$" 2>/dev/null || true); do
        width="$(xdotool getwindowgeometry --shell "${id}" 2>/dev/null \
                 | sed -n 's/^WIDTH=//p')"
        if [[ -n "${width}" ]] && (( width > 100 )); then
            echo "${id}"
            return 0
        fi
    done
    return 1
}

ball_win() {
    # 输出悬浮球窗口 id（PIXIU 中宽度≤100 的窗口）。
    local id width
    for id in $(xdotool search --name "^PIXIU$" 2>/dev/null || true); do
        width="$(xdotool getwindowgeometry --shell "${id}" 2>/dev/null \
                 | sed -n 's/^WIDTH=//p')"
        if [[ -n "${width}" ]] && (( width <= 100 )); then
            echo "${id}"
            return 0
        fi
    done
    return 1
}

chat_origin() {
    # 输出 "x y"：聊天窗左上角（XWayland 逻辑坐标）。
    local id
    id="$(chat_win)"
    xdotool getwindowgeometry --shell "${id}" 2>/dev/null \
        | sed -n 's/^X=//p; s/^Y=//p' \
        | tr '\n' ' '
}

close_target() {
    # 关闭/隐藏已打开的目标窗口：激活后发送 Escape。
    # 记忆面板 Esc=隐藏，设置/录入对话框 Esc=关闭，语义一致。
    if win_visible "$1"; then
        wmctrl -a "$1" >/dev/null 2>&1 || true
        sleep 0.3
        xdotool key --clearmodifiers Escape
        sleep 0.4
    fi
}

check_entry() {
    local name="$1" dx="$2" pattern="$3"
    local origin gx gy
    origin="$(chat_origin)"
    gx=$(( $(echo "${origin}" | awk '{print $1}') + dx ))
    gy=$(( $(echo "${origin}" | awk '{print $2}') + CHIP_Y ))

    close_target "记忆管理"
    close_target "设置"
    close_target "录入记忆"

    # 只点击一次：若首击被焦点逻辑吞掉，目标窗口不会出现。
    xdotool mousemove --sync "${gx}" "${gy}"
    sleep 0.3
    xdotool click 1
    sleep 0.9

    if win_visible "${pattern}"; then
        log "PASS: ${name} 首击即打开目标窗口"
        pass_count=$((pass_count + 1))
    else
        log "FAIL: ${name} 首击后未出现目标窗口（${pattern}）"
        fail_count=$((fail_count + 1))
    fi
    close_target "${pattern}"
}

if ! command -v xdotool >/dev/null 2>&1 || ! command -v xwininfo >/dev/null 2>&1 \
   || ! command -v wmctrl >/dev/null 2>&1; then
    log "需要 xdotool / xwininfo / wmctrl，请先安装"
    exit 2
fi

# 1) 唤起聊天窗
if ! chat_win >/dev/null || ! xwininfo -id "$(chat_win)" 2>/dev/null \
       | grep -q "Map State: IsViewable"; then
    log "聊天窗不可见，点击悬浮球唤起"
    ball="$(ball_win || true)"
    if [[ -z "${ball}" ]]; then
        log "找不到悬浮球窗口，无法唤起聊天窗"
        exit 2
    fi
    bx="$(xdotool getwindowgeometry --shell "${ball}" | sed -n 's/^X=//p')"
    by="$(xdotool getwindowgeometry --shell "${ball}" | sed -n 's/^Y=//p')"
    xdotool mousemove --sync $((bx + 28)) $((by + 28))
    sleep 0.3
    xdotool click 1
    sleep 0.8
fi
if ! chat_win >/dev/null || ! xwininfo -id "$(chat_win)" 2>/dev/null \
       | grep -q "Map State: IsViewable"; then
    log "聊天窗仍不可见，无法继续"
    exit 2
fi

# 2) 焦点目标窗口：点击它让聊天窗失去激活
xmessage -geometry 240x120+100+100 "focus target" >/dev/null 2>&1 &
xm_pid=$!
sleep 0.5
xm="$(xdotool search --name "focus target" 2>/dev/null | head -1 || true)"
if [[ -n "${xm}" ]]; then
    xmx="$(xdotool getwindowgeometry --shell "${xm}" | sed -n 's/^X=//p')"
    xmy="$(xdotool getwindowgeometry --shell "${xm}" | sed -n 's/^Y=//p')"
    xdotool mousemove --sync $((xmx + 120)) $((xmy + 60))
    sleep 0.3
    xdotool click 1
    sleep 0.5
fi

# 3) 逐个首击验证（同步入口设计归属：打开记忆面板并切到“同步”Tab，
#    与“记忆”共用同一目标窗口标题）。
check_entry "记忆" "${CHIP_MEMORY_X}" "记忆管理"
check_entry "设置" "${CHIP_SETTINGS_X}" "设置"
check_entry "录入" "${CHIP_IMPORT_X}" "录入记忆"
check_entry "同步" "${CHIP_SYNC_X}" "记忆管理"

kill "${xm_pid}" >/dev/null 2>&1 || true

log "结果: ${pass_count} PASS / ${fail_count} FAIL"
[[ ${fail_count} -eq 0 ]]
