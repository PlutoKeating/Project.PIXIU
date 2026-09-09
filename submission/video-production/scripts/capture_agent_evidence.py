#!/usr/bin/env python3
"""Extract tool events from one explicitly selected public demo session."""
import argparse
import json
from pathlib import Path
import shlex
import subprocess

REMOTE = r'''
import urllib.request,json,hashlib,pathlib,sys
args=json.load(sys.stdin)
with urllib.request.urlopen('http://127.0.0.1:8642/api/sessions/'+args['session_id']+'/details',timeout=20) as r: detail=json.load(r)
events=[]; models=[]
for line in detail['content'].splitlines():
 try: event=json.loads(line)
 except ValueError: continue
 if str(event.get('event','')).startswith('tool.execution'): events.append(event)
 if event.get('event')=='model.request':
  data=event['data'];models.append({'model':data.get('model'),'tools':[t.get('name') for t in data.get('tools',[])]})
result={'session_id':args['session_id'],'source_log_sha256':hashlib.sha256(detail['content'].encode()).hexdigest(),'tool_events':events,'model_requests':models,'model_request_filter':'仅保留模型名与提供的工具名；省略工具schema及系统消息'}
if args.get('artifact'):
 p=pathlib.Path(args['artifact']);raw=p.read_bytes() if p.exists() else None
 result['artifact']={'path':args['artifact'],'exists':raw is not None,'content':raw.decode() if raw is not None else None,'sha256':hashlib.sha256(raw).hexdigest() if raw is not None else None}
print(json.dumps(result,ensure_ascii=False))
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--guest', required=True)
    parser.add_argument('--session-id', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--artifact', help='An explicitly selected public demonstration artifact')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output exists; preserve previous evidence')
    result = subprocess.run(['ssh', '-o', 'BatchMode=yes', args.guest,
                             'python3 -c ' + shlex.quote(REMOTE)],
                            input=json.dumps({'session_id': args.session_id, 'artifact': args.artifact}),
                            capture_output=True, text=True, check=True)
    report = json.loads(result.stdout.strip().splitlines()[-1])
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    print('已提取工具事件', len(report['tool_events']))


if __name__ == '__main__':
    main()
