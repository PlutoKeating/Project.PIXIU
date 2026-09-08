#!/usr/bin/env python3
"""Exercise writes and lifecycle through the installed public API.

All input is synthetic Chinese demonstration data, in a dedicated local scope.
This records API evidence; it does not pretend that a UI or automatic policy
performed these explicitly requested lifecycle promotions.
Knowledge kind is checked separately through a read-only SQLite connection;
the public context API intentionally does not expose that metadata.
"""
import argparse
import json
from pathlib import Path
import shlex
import subprocess
import time
from demo_api import call

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--guest', required=True)
parser.add_argument('--output', type=Path, required=True)
parser.add_argument('--database-relative', required=True, help='Demo DB path relative to guest home, for read-only kind audit')
args = parser.parse_args()
if args.output.exists():
    parser.error('Output exists')
scope = 'user:video-structure-v4'
records = []


def save(status='in_progress'):
    args.output.write_text(json.dumps({
        'environment': 'V11 虚拟机，公共 API 合成数据实测；知识类型另作只读数据库核对',
        'status': status, 'records': records,
    }, ensure_ascii=False, indent=2) + '\n')


def request(label, path, data):
    result = call(args.guest, path, data)
    records.append({'label': label, 'path': path, 'input': data, 'output': result})
    save()
    assert result['status'] == 200, result
    return result['body']


examples = [
    ('FACT', '家庭公共物品位置', {'内容': '备用电池放在书房左侧抽屉。'}),
    ('WORKFLOW', '月末账单核对流程', {'steps': ['整理账单', '核对金额', '汇总支出']}),
    ('CASE', '投影连接故障案例', {'case': {'问题': '投影没有画面', '处理': '重新选择输入源', '结果': '画面恢复'}}),
    ('TEMPLATE', '家庭周计划模板', {'template': {'本周事项': '', '负责人': '', '完成时间': ''}}),
]
for kind, title, body in examples:
    request('写入' + title, '/memory/write', {'source_type': 'MANUAL_CONFIG',
            'raw': {'title': title, 'body': body}, 'scope': scope})
    context = request('检索' + title, '/agent/context', {
        'query': title, 'scope': scope, 'session_id': 'video-kinds',
        'turn_id': 'kind-' + kind, 'top_k': 1, 'max_chars': 2000})
    assert context['items'], context
    # Public context deliberately omits kind; audit this metadata read-only,
    # instead of pretending a response field exists or modifying the product API.
    code = '''import json,sqlite3,sys
from pathlib import Path
data=json.load(sys.stdin)
path=(Path.home()/data["database"]).resolve()
with sqlite3.connect(path.as_uri()+"?mode=ro",uri=True) as db:
 row=db.execute("SELECT kind FROM knowledge_items WHERE id=? AND scope=?", (data["id"],data["scope"])).fetchone()
 print(json.dumps({"kind":row[0] if row else None}))
'''
    audit = subprocess.run(['ssh', args.guest, 'python3 -c ' + shlex.quote(code)],
                           input=json.dumps({'database': args.database_relative,
                                             'id': context['items'][0]['knowledge_id'], 'scope': scope}),
                           capture_output=True, text=True, check=True)
    actual_kind = json.loads(audit.stdout)['kind']
    records.append({'label': '只读数据库类型核对', 'expected': kind, 'actual': actual_kind})
    save()
    assert actual_kind == kind
    print(title, kind, '已验证', flush=True)

for event, tier, label in [('TURN_END', 'SHORT_TERM', '本轮任务要点'),
                            ('PRE_COMPRESS', 'MID_TERM', '本次会话整理摘要')]:
    context = request(label, '/agent/lifecycle', {
        'event': event, 'scope': scope, 'session_id': 'video-lifecycle',
        'run_id': 'video-run', 'turn_id': 'video-turn', 'occurred_at': int(time.time()),
        'idempotency_key': 'video-lifecycle-' + event,
        'data': {'source_type': 'MANUAL_CONFIG', 'raw': {'title': label,
                 'body': {'内容': '已核对账单，接下来按月份归档。'}}}})
    assert context['tier'] == tier
    promoted = request(label + '显式晋升', '/memory/flow/promote', {
        'source': tier, 'scope': scope, 'context_ids': [context['context_id']]})
    assert promoted['promoted_count'] == 1 and len(promoted['knowledge_ids']) == 1
    query = request(label + '长期检索', '/memory/query', {
        'text': label, 'context_hint': {'scope': scope}})
    assert query['source_knowledge'] == promoted['knowledge_ids'][0], query
    print(tier, '显式晋升后可检索', flush=True)

save('verified')
