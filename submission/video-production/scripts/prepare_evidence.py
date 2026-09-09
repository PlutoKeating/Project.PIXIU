#!/usr/bin/env python3
"""Copy named, preserved observations into the video; never simulate states."""
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REPO = ROOT.parents[1]
source = ROOT / 'raw/network/第二轮断连并发与遗忘传播.json'
observations = json.loads(source.read_text())
events = observations['events']


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

named = {event['step']: event for event in events}
online = named['在线笔记本不再返回有效条目']
offline = named['断连客厅尚未收到遗忘']
rejoined = named['客厅重连后条目失效']
tombstones = named['三端墓碑诊断']['result']
queries = observations['post_forget_queries']
assert online['result']['status'] == rejoined['result']['status'] == 404
assert offline['result']['status'] == 200
assert len(tombstones) == 3
assert all(r['status'] == 200 and r['body']['tombstone'] for r in tombstones)
assert len({r['body']['operation_digest'] for r in tombstones}) == 1
assert len(queries) == 3
assert all(q['query']['status'] == 200 and q['query']['body']['answer'] == ''
           and q['query']['body']['source_evidence'] == []
           and q['query']['body']['source_knowledge'] == '' for q in queries)
forget = {'source': trace['source'], 'sha256': trace['sha256'],
          'online': online, 'offline': offline, 'rejoined': rejoined,
          'tombstones': tombstones, 'queries': queries}
(ROOT / 'src/forget-trace.json').write_text(json.dumps(forget, ensure_ascii=False, indent=2) + '\n')

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
print('已从原始证据生成同步与遗忘检查点、四项历史评测数据')

# Keep the complete request parameters beside displayed privacy observations.
privacy_source = ROOT / 'raw/network/共享边界请求与响应-01.json'
privacy = json.loads(privacy_source.read_text())
records = privacy['records']
by_label = {r['label']: r for r in records}
written = by_label['私有写入']
query = by_label['本机查询']
assert written['response']['status'] == query['response']['status'] == 200
assert written['request']['body']['scope'] == query['request']['body']['context_hint']['scope']
assert query['response']['body']['source_evidence'] == [written['response']['body']['evidence_id']]
knowledge = query['response']['body']['source_knowledge']
remote = [r for r in records if r['label'] == '另一端按同一ID与范围读取']
assert len(remote) == 2
assert all(r['response']['status'] == 404 and r['request']['path'] ==
           f"/memory/items/{knowledge}?scope={written['request']['body']['scope']}" for r in remote)
state = by_label['私有条目同步状态']
assert state['request']['path'] == f'/sync/state/knowledge/{knowledge}'
assert state['response']['status'] == 200 and state['response']['body']['present'] is False
denied = by_label['合成敏感输入共享拒绝']
assert denied['request']['body']['scope'] == 'shared:home'
assert denied['response']['status'] == 422
assert denied['response']['body']['error'] == 'SENSITIVE_SHARED_SCOPE'
(ROOT / 'src/privacy-boundary.json').write_bytes(privacy_source.read_bytes())
print('已核对私有与敏感共享边界请求参数并复制原始记录')

source = ROOT / 'raw/network/接入清洗与质量-01.json'
ingest = json.loads(source.read_text())
written, detail, queried = [r['response'] for r in ingest['records']]
assert written['status'] == detail['status'] == queried['status'] == 200
assert queried['body']['source_evidence'] == [written['body']['evidence_id']]
cleaned = detail['body']['raw']
assert cleaned['title'] == '家庭物品整理演示'
assert cleaned['body']['items'] == ['核对书目', '归还原位']
assert '备注' not in cleaned['body']
output = {'source': str(source.relative_to(ROOT)),
          'sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
          'title': cleaned['title'], 'items': cleaned['body']['items'],
          'input_items': ingest['records'][0]['request']['body']['raw']['body']['items'],
          'quality': detail['body']['quality_score'], 'sensitivity': detail['body']['sensitivity']}
(ROOT / 'src/ingest-results.json').write_text(json.dumps(output, ensure_ascii=False, indent=2) + '\n')
print('已核对接入清洗、质量与同来源检索')

source = ROOT / 'raw/network/生命周期摘要晋升与复用-01.json'
flow = json.loads(source.read_text())['records']
assert len(flow) == 8
cases = []
for offset, tier in [(0, 'SHORT_TERM'), (4, 'MID_TERM')]:
    created, promoted, reused, detail = flow[offset:offset + 4]
    assert all(r['response']['status'] == 200 for r in (created, promoted, reused, detail))
    context = created['response']['body']
    promotion = promoted['response']['body']
    answer = reused['response']['body']
    item = answer['items'][0]
    evidence = detail['response']['body']
    assert context['tier'] == promoted['request']['body']['source'] == tier
    assert promoted['request']['body']['context_ids'] == [context['context_id']]
    assert promotion['promoted_count'] == 1
    assert promotion['knowledge_ids'] == [item['knowledge_id']]
    assert item['evidence_ids'] == [evidence['id']]
    summary = created['request']['body']['data']['summary']
    assert evidence['raw']['body']['data']['summary'] == summary
    assert summary in answer['context'] and answer['truncated'] is False
    assert len(answer['context']) <= reused['request']['body']['max_chars']
    cases.append({'tier': tier, 'event': context['event'], 'summary': summary,
                  'context_id': context['context_id'], 'knowledge_id': item['knowledge_id'],
                  'evidence_id': evidence['id'], 'title': item['title'],
                  'promoted_count': promotion['promoted_count'],
                  'max_chars': reused['request']['body']['max_chars']})
(ROOT / 'src/flow-results.json').write_text(json.dumps({
    'source': str(source.relative_to(ROOT)),
    'sha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'cases': cases,
}, ensure_ascii=False, indent=2) + '\n')
print('已核对短中期晋升、知识与证据ID、摘要完整性及字符预算')

source = ROOT / 'raw/network/四类知识长正文-01.json'
examples = json.loads(source.read_text())['records']
kinds = json.loads((ROOT / 'raw/network/四类知识长正文-类型复核-01.json').read_text())['records']
quotes = ['书房共有三层书架。', '从借阅登记本逐项核对书名',
          '把常用工具书集中到中层', '填写本周共同阅读的主题']
assert len(examples) == len(kinds) == len(quotes) == 4
output = []
for example, kind, quote in zip(examples, kinds, quotes):
    written, queried, detail = example['calls']
    assert all(r['response']['status'] == 200 for r in example['calls'])
    evidence = detail['response']['body']
    item = queried['response']['body']['items'][0]
    assert item['evidence_ids'] == [written['response']['body']['evidence_id']] == [evidence['id']]
    assert evidence['raw']['body'] == written['request']['body']['raw']['body']
    assert quote in json.dumps(evidence['raw']['body'], ensure_ascii=False)
    assert kind['actual'] == kind['expected'] == example['expected_kind']
    assert item['knowledge_id'] == kind['id']
    output.append({'title': example['title'], 'kind': kind['actual'], 'quote': quote,
                   'knowledge_id': kind['id'], 'evidence_id': evidence['id']})
(ROOT / 'src/knowledge-examples.json').write_text(json.dumps({
    'source': str(source.relative_to(ROOT)),
    'sha256': hashlib.sha256(source.read_bytes()).hexdigest(), 'examples': output,
}, ensure_ascii=False, indent=2) + '\n')
print('已核对四类知识的正文、摘录、类型与来源ID')

source = ROOT / 'raw/network/语义冲突审计-01.json'
record = json.loads(source.read_text())
assert record['status'] == 'verified' and record['audit']['http_status'] == 200
assert all(c['response']['status'] == 200 for c in record['calls'])
old, new = [record['calls'][i]['response']['body']['items'][0] for i in (1, 4)]
audit = record['audit']['records'][0]
assert audit['target_knowledge'] == old['knowledge_id'] != new['knowledge_id']
for index, item in ((0, old), (3, new)):
    evidence = record['calls'][index]['response']['body']['evidence_id']
    assert item['evidence_ids'] == [evidence]
    detail = record['calls'][index + 2]['response']['body']
    assert detail['id'] == evidence
    assert detail['raw']['body'] == record['calls'][index]['request']['body']['raw']['body']
    assert detail['raw']['body']['层数'] == (3 if index == 0 else 4)
assert audit['old_value'] == 3 and audit['new_value'] == 4
assert audit['resolution'] == 'NEW_WINS' and audit['severity'] == 'medium'
(ROOT / 'src/semantic-conflict.json').write_text(json.dumps({
    'source': str(source.relative_to(ROOT)),
    'sha256': hashlib.sha256(source.read_bytes()).hexdigest(), **audit,
}, ensure_ascii=False, indent=2) + '\n')
print('已核对语义冲突原值、裁决与新旧知识来源')
