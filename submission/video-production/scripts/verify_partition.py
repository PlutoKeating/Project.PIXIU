#!/usr/bin/env python3
"""Verify real sync partition and reconciliation on three isolated demo guests.

Uses temporary firewall rules on guest C's sync TCP port only; SSH and mDNS stay
available. Removes precisely those rules in finally. Never flushes a firewall.
Results describe API observations, not screen footage or physical-device gates.
"""
import argparse
import datetime
import json
from pathlib import Path
import subprocess
import time
from demo_api import call

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--guests', nargs=3, required=True)
parser.add_argument('--knowledge', required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
if args.output.exists():
    parser.error('Output already exists')
a, b, c = args.guests
events = []
active_rules = []


def save(label, value):
    events.append({'time': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                   'step': label, 'result': value})
    args.output.write_text(json.dumps({
        'environment': '同宿主三台 V11 虚拟机；开发源码加载，正式包待重建；运行后另记录实际源码摘要',
        'partition': '仅阻断客厅设备同步 TCP 端口；SSH 与设备广播保留',
        'final_device_evidence': False, 'events': events,
    }, ensure_ascii=False, indent=2) + '\n')
    print(label, flush=True)


def snapshot(guest):
    return call(guest, '/memory/items/' + args.knowledge + '?scope=shared:home')


def partition():
    for direction in ('INPUT', 'OUTPUT'):
        rule = [direction, '-p', 'tcp', '--dport', '8766', '-m', 'comment',
                '--comment', 'pixiu-video-partition', '-j', 'REJECT']
        subprocess.run(['ssh', c, 'sudo', '-n', 'iptables', '-I', *rule], check=True)
        active_rules.append(rule)
    save('阻断客厅同步连接', {'rules': len(active_rules)})


def reconnect():
    while active_rules:
        rule = active_rules[-1]
        subprocess.run(['ssh', c, 'sudo', '-n', 'iptables', '-D', *rule], check=True)
        active_rules.pop()
    save('恢复客厅同步连接', {'remaining_demo_rules': 0})


def wait_for(label, predicate, seconds=100):
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline:
        value = predicate()
        if value:
            save(label, value)
            return value
        time.sleep(3)
    raise RuntimeError('Timed out: ' + label)


def update(guest, version, text, key):
    result = call(guest, '/memory/update', {
        'knowledge_id': args.knowledge, 'scope': 'shared:home',
        'expected_version': version, 'body': {'内容': text},
        'idempotency_key': key,
    })
    assert result['status'] == 200, result
    return result


try:
    baseline = [snapshot(g) for g in args.guests]
    assert all(r['status'] == 200 for r in baseline)
    version = baseline[0]['body']['version']
    assert all(r['body']['version'] == version for r in baseline)
    save('三端初始版本一致', baseline)
    partition()
    update(a, version, '每天晚上九点半关闭书房空调，周末检查客厅灯具。', 'video-offline-01')
    wait_for('在线笔记本收到更新', lambda: (r if (r := snapshot(b))['body'].get('version') == version + 1 else None))
    stale = snapshot(c)
    assert stale['body']['version'] == version
    save('断连客厅仍保留旧版本', stale)
    reconnect()
    wait_for('客厅重连补齐更新', lambda: (r if (r := snapshot(c))['body'].get('version') == version + 1 else None))
    partition()
    update(a, version + 1, '书房方案：晚上九点关闭空调。', 'video-concurrent-a')
    update(c, version + 1, '客厅方案：晚上九点四十五关闭空调。', 'video-concurrent-c')
    save('断连期间两端分别修改同一版本', [snapshot(a), snapshot(c)])
    reconnect()

    def converged():
        rows = [snapshot(g) for g in args.guests]
        if all(r['status'] == 200 for r in rows) and len({json.dumps(r['body']['body'], sort_keys=True) for r in rows}) == 1:
            return rows
        return None

    wait_for('并发修改三端正文收敛', converged)
    partition()
    preview = call(a, '/forget', {'command': '忘记家庭节能约定', 'confirm': False, 'scope': 'shared:home'})
    assert preview['status'] == 200, preview
    assert {t['id'] for t in preview['body']['targets']} == {args.knowledge}
    token = preview['body'].pop('confirmation_token')
    save('预览遗忘范围', preview)
    result = call(a, '/forget', {'command': '忘记家庭节能约定', 'confirm': True,
                                'scope': 'shared:home', 'confirmation_token': token})
    assert result['status'] == 200, result
    save('确认遗忘', result)
    wait_for('在线笔记本不再返回有效条目', lambda: (r if (r := snapshot(b))['status'] == 404 else None))
    assert snapshot(c)['status'] == 200
    save('断连客厅尚未收到遗忘', snapshot(c))
    reconnect()
    wait_for('客厅重连后条目失效', lambda: (r if (r := snapshot(c))['status'] == 404 else None))
    save('三端墓碑诊断', [call(g, '/sync/state/knowledge/' + args.knowledge) for g in args.guests])
    save('完成', {'offline_recovery': True, 'concurrent_convergence': True, 'forget_propagation': True})
except Exception as error:
    save('未通过', {'error': str(error), 'type': type(error).__name__})
    raise
finally:
    if active_rules:
        reconnect()
