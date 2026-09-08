#!/usr/bin/env python3
"""Copy named, preserved observations into the video; never simulate states."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
source = ROOT / 'raw/network/第二轮断连并发与遗忘传播.json'
events = json.loads(source.read_text())['events']


def row(event, device, index=None):
    result = events[event]['result']
    if index is not None:
        result = result[index]
    assert result['status'] == 200
    body = result['body']
    return {'device': device, 'time': events[event]['time'],
            'version': body['version'], 'text': body['body']['内容'],
            'knowledge_id': body['knowledge_id'], 'status': result['status']}


devices = ['书房工作站', '随身笔记本', '客厅一体机']
trace = {
    'source': str(source.relative_to(ROOT)),
    'sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
    'offline': [
        {'label': '同一条节能约定，三端均为版本一',
         'rows': [row(0, d, i) for i, d in enumerate(devices)]},
        {'label': '同步中断期间：在线端更新，客厅保留旧版',
         'rows': [row(2, devices[1]), row(3, devices[2])]},
        {'label': '恢复同步后：客厅读到版本二',
         'rows': [row(2, devices[1]), row(5, devices[2])]},
    ],
    'concurrent': [
        {'label': '从同一版本分别修改，形成两个版本三',
         'rows': [row(7, devices[0], 0), row(7, devices[2], 1)]},
        {'label': '恢复连接后：三端正文收敛',
         'rows': [row(9, d, i) for i, d in enumerate(devices)]},
    ],
}
assert len({r['knowledge_id'] for group in ('offline', 'concurrent')
            for stage in trace[group] for r in stage['rows']}) == 1
assert len({r['text'] for r in trace['concurrent'][-1]['rows']}) == 1
(ROOT / 'src/sync-trace.json').write_text(json.dumps(trace, ensure_ascii=False, indent=2) + '\n')

source = REPO / 'docs/acceptance/acceptance-baseline-2026-08-24.json'
baseline = json.loads(source.read_text())
labels = {'preference_accuracy': '偏好准确率', 'knowledge_recall_at_k': '知识召回率',
          'retrieval_p95_ms': '检索延迟 P95', 'conflict_accuracy': '冲突正确率'}
output = {'source': str(source.relative_to(REPO)),
          'sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
          'dataset': baseline['dataset_name'],
          'metrics': [{**m, 'label': labels[m['name']]} for m in baseline['metrics']
                      if m['name'] in labels]}
assert len(output['metrics']) == 4
(ROOT / 'src/evaluation-baseline.json').write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
print('已从原始证据生成同步检查点与四项历史评测数据')
