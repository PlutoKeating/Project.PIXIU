#!/usr/bin/env python3
"""Capture two missing preference categories using explicitly synthetic API inputs."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.parse import quote

from demo_api import call

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--guest', required=True)
parser.add_argument('--output', type=Path, required=True)
args = parser.parse_args()
if args.output.exists():
    parser.error('Preserve prior evidence; output already exists')
scope = 'user:video-preference-4k-v1'
events = []


def request(label, path, data=None):
    result = call(args.guest, path, data)
    events.append({'label': label, 'recorded_at': datetime.now(timezone.utc).isoformat(),
                   'path': path, 'input': data, 'output': result})
    args.output.write_text(json.dumps({'scope': scope,
        'method': '合成行为与配置经公共接口提取；不证明真实热键监听或安全策略执行',
        'events': events}, ensure_ascii=False, indent=2) + '\n')
    if result['status'] != 200:
        raise RuntimeError(f'{label}: HTTP {result["status"]}')
    return result['body']


before = request('读取原有输出风格版本', '/preferences?scope=' + quote(scope))['preferences']
styles = [p for p in before if p['category'] == 'OUTPUT_STYLE']
if len(styles) != 1 or styles[0]['version'] != 3:
    raise RuntimeError('Expected the existing version-3 output style; inspect before writing')
for category, source, raw in [
    ('OP_HABIT', 'USER_BEHAVIOR', {'title': '公开操作习惯演示',
        'events': [{'action': 'hotkey'}, {'action': 'hotkey'}, {'action': 'hotkey'}]}),
    ('SECURITY_POLICY', 'MANUAL_CONFIG', {'title': '公开安全策略演示',
        'body': {'no_exfiltrate': True}}),
]:
    if any(p['category'] == category for p in before):
        continue
    written = request('写入合成样例：' + category, '/memory/write', {
        'source_type': source, 'scope': scope, 'raw': raw,
        'idempotency_key': 'video-preference-categories-v2:' + category})
    if not written.get('preference_count'):
        request('显式提取：' + category, '/preference/extract',
                {'evidence_ids': [written['evidence_id']]})
after = request('读取三类偏好实际结果', '/preferences?scope=' + quote(scope))['preferences']
if {p['category'] for p in after} != {'OP_HABIT', 'OUTPUT_STYLE', 'SECURITY_POLICY'}:
    raise RuntimeError('Missing category; inspect captured results')
style = next(p for p in after if p['category'] == 'OUTPUT_STYLE')
if style != styles[0]:
    raise RuntimeError('Output style unexpectedly changed')
for pref in after:
    request('读取版本历史：' + pref['category'], '/preference/' + pref['id'] + '/history')
print(json.dumps([{'category': p['category'], 'value': p['value'], 'version': p['version']}
                  for p in after], ensure_ascii=False))
