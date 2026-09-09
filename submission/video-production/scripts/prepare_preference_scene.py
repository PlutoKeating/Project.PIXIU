#!/usr/bin/env python3
"""Bind the supplementary preference cards to captured public API results."""
import hashlib
import json
from pathlib import Path

root = Path(__file__).resolve().parents[1]
source = root / 'raw/偏好三类提取-02.json'
capture = json.loads(source.read_text())
event = next(e for e in capture['events'] if e['label'] == '读取三类偏好实际结果')
assert event['output']['status'] == 200
rows = event['output']['body']['preferences']
expected = {
    'OP_HABIT': ('操作习惯', '合成行为事件', 'op_habit.prefer_hotkey', {'enabled': True, 'signal_count': 1}, 1),
    'SECURITY_POLICY': ('安全策略', '合成手动配置', 'security.no_exfiltrate', {'no_exfiltrate': True}, 1),
}
cards = []
for category, (title, origin, key, value, version) in expected.items():
    pref = next(p for p in rows if p['category'] == category)
    assert pref['key'] == key and pref['value'] == value and pref['version'] == version
    history = next(e for e in capture['events'] if e['label'] == '读取版本历史：' + category)
    assert history['output']['status'] == 200
    assert history['output']['body']['current_version'] == version
    cards.append({**pref, 'title': title, 'origin': origin})
(root / 'src/preference-categories.json').write_text(json.dumps({
    'source': str(source.relative_to(root)), 'sha256': hashlib.sha256(source.read_bytes()).hexdigest(),
    'cards': cards,
}, ensure_ascii=False, indent=2) + '\n')
print('Bound two preference categories and their version histories to captured evidence.')
