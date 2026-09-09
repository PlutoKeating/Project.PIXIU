#!/usr/bin/env python3
"""Capture a synthetic same-entity correction through the installed public API."""
import argparse
import json
from pathlib import Path
import time

from demo_api import call


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--guest', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output exists; preserve the previous evidence')
    title = '家庭书架层数核对'
    scope = 'user:local'
    report = {'environment': 'V11虚拟机公共接口；公开合成资料，本机个人范围',
              'title': title, 'scope': scope, 'status': 'in_progress', 'calls': []}

    def save():
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')

    def request(path, body=None):
        response = call(args.guest, path, body)
        report['calls'].append({'recorded_at': time.time(), 'request': {
            'method': 'GET' if body is None else 'POST', 'path': path, 'body': body},
            'response': response})
        save()
        assert response['status'] == 200, response['status']
        return response['body']

    items = []
    for count in (3, 4):
        written = request('/memory/write', {
            'source_type': 'MANUAL_CONFIG', 'scope': scope,
            'idempotency_key': f'video-semantic-v1-{count}',
            'raw': {'title': title, 'body': {'entity': '演示书房公共书架', '层数': count}}})
        queried = request('/agent/context', {
            'query': title, 'scope': scope, 'session_id': 'video-semantic-v1',
            'turn_id': str(count), 'top_k': 1, 'max_chars': 2000})
        item = queried['items'][0]
        assert item['title'] == title and item['evidence_ids'] == [written['evidence_id']]
        detail = request('/evidence/' + written['evidence_id'])
        assert detail['raw']['body']['层数'] == count
        items.append(item)

    # The endpoint has no scope filter. Preserve the exact relevant record,
    # explicitly recording omission of unrelated entries instead of publishing them.
    response = call(args.guest, '/conflicts')
    assert response['status'] == 200
    all_records = response['body']['conflicts']
    selected = [r for r in all_records if r['target_knowledge'] == items[0]['knowledge_id']]
    report['audit'] = {'request': {'method': 'GET', 'path': '/conflicts'},
                       'http_status': response['status'], 'records': selected,
                       'response_filter': {'target_knowledge': items[0]['knowledge_id'],
                                           'omitted_unrelated_count': len(all_records) - len(selected)}}
    save()
    assert len(selected) == 1
    audit = selected[0]
    assert audit['old_value'] == 3 and audit['new_value'] == 4
    assert audit['resolution'] == 'NEW_WINS' and audit['severity'] == 'medium'
    assert items[0]['knowledge_id'] != items[1]['knowledge_id']
    report['status'] = 'verified'
    save()
    print('同实体层数3→4、来源及NEW_WINS审计已核对')


if __name__ == '__main__':
    main()
