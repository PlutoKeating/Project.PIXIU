#!/usr/bin/env python3
"""Extract the two separately labelled Agent demonstrations from preserved logs."""
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
sources = {}


def read(name):
    path = ROOT / name
    sources[name] = hashlib.sha256(path.read_bytes()).hexdigest()
    return json.loads(path.read_text())


def completed(record, name):
    events = [event['data'] for event in record['tool_events']
              if event['event'] == 'tool.execution.completed' and event['data']['name'] == name]
    assert len(events) == 1 and not events[0]['is_error']
    return events[0], json.loads(events[0]['result'])


gateway = read('raw/network/完整助手任务-03-工具证据.json')
native = read('raw/network/秋季原生助手任务-工具证据-02.json')
reuse = read('review/秋季任务保存复用验证-01.json')
_, terminal = completed(gateway, 'terminal')
assert terminal['exit_code'] == 0 and terminal['output'] == '100'
_, search = completed(gateway, 'web_search')
assert search['success']
site = next(row for row in search['data']['web'] if row['url'] == 'https://www.openkylin.top/')
save, saved = completed(native, 'pixiu_memory_remember')
assert saved['status'] == 'accepted'
assert saved['evidence_id'] == reuse['stored_evidence_id']
assert reuse['reused_knowledge_id'] == reuse['native_final_citation_seen']
for record, artifact in [(gateway, '阅读预算-第三轮.txt'), (native, '秋季复核单.txt')]:
    path = ROOT / 'raw/artifacts' / artifact
    assert hashlib.sha256(path.read_bytes()).hexdigest() == record['artifact']['sha256']
    assert path.read_text() == record['artifact']['content']
    assert len(path.read_text().splitlines()) == 4
image = '20260909-秋季复用记忆工具卡-4K.png'
source_image = ROOT / 'raw/screenshots' / image
sources[str(source_image.relative_to(ROOT))] = hashlib.sha256(source_image.read_bytes()).hexdigest()
shutil.copyfile(source_image, ROOT / 'public/screens' / image)
(ROOT / 'src/agent-task.json').write_text(json.dumps({
    'sources': sources,
    'gateway': {'file': gateway['artifact']['content'], 'search_title': site['title'], 'search_url': site['url']},
    'native': {'file': native['artifact']['content'], 'saved_content': save['arguments']['content'],
               'knowledge_id': reuse['reused_knowledge_id'], 'screenshot': image},
    'boundary': '两个独立样本；原生搜索失败，不展示为成功；新会话使用显式记忆检索。',
}, ensure_ascii=False, indent=2) + '\n')
print('网关工具结果、原生保存与引用、原始文件及截图摘要已核对')
