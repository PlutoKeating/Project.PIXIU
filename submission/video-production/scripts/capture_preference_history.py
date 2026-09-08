#!/usr/bin/env python3
"""Record initial extraction/re-extraction or a later synthetic style update."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from urllib.parse import quote
from demo_api import call

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--guest', required=True)
parser.add_argument('--stage', type=int, choices=(1, 3), required=True,
                    help='1 writes/re-extracts compact (versions 1/2); 3 writes verbose')
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
    args.output.write_text(json.dumps({'scope': scope, 'stage': args.stage,
        'method': '合成配置经公共接口写入；事件逐项区分写入提取与显式重复提取',
        'events': events}, ensure_ascii=False, indent=2) + '\n')
    if result['status'] != 200:
        raise RuntimeError(f'{label}: HTTP {result["status"]}')
    return result['body']


before = request('提取前读取偏好', '/preferences?scope=' + quote(scope))['preferences']
if args.stage == 1 and before:
    raise RuntimeError('Scope already populated; do not duplicate the first extraction')
if args.stage > 1 and (len(before) != 1 or before[0]['version'] != args.stage - 1):
    raise RuntimeError('Unexpected previous version; inspect evidence before proceeding')
detail = '简洁回答' if args.stage == 1 else '详细说明'
written = request('写入回答风格配置', '/memory/write', {
    'source_type': 'MANUAL_CONFIG', 'scope': scope,
    'raw': {'title': '回答风格演示', 'body': {'detail_level': detail}},
    'idempotency_key': f'video-preference-4k-v1:{args.stage}'})
if args.stage == 1 or not written.get('preference_count'):
    request('显式提取当前证据', '/preference/extract', {'evidence_ids': [written['evidence_id']]})
after = request('读取提取后的偏好', '/preferences?scope=' + quote(scope))['preferences']
if len(after) != 1:
    raise RuntimeError('Expected one preference; inspect extraction result')
history = request('读取版本历史', '/preference/' + after[0]['id'] + '/history')
print(json.dumps({'stage': args.stage, 'current_version': history['current_version'],
                  'value': after[0]['value'], 'history_rows': len(history['history'])}, ensure_ascii=False))
