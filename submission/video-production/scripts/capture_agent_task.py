#!/usr/bin/env python3
"""Run a public demonstration task through the installed Agent gateway."""
import argparse
import json
from pathlib import Path
import shlex
import subprocess


REMOTE = r'''
import json,sys,urllib.request,urllib.error,time,pathlib,subprocess
task=json.load(sys.stdin)
pid=subprocess.check_output(['systemctl','--user','show','kylin-agent-runtime-gateway.service','-p','MainPID','--value'],text=True).strip()
env=dict(x.split('=',1) for x in pathlib.Path('/proc/'+pid+'/environ').read_bytes().decode().split(chr(0)) if '=' in x)
key=env.get('API_SERVER_KEY','')
headers={'Content-Type':'application/json'}
if key: headers['Authorization']='Bearer '+key
def call(path,body,extra=None):
 req=urllib.request.Request('http://127.0.0.1:8642'+path,data=json.dumps(body).encode(),headers={**headers,**(extra or {})})
 with urllib.request.urlopen(req,timeout=1200) as response: return response.status,json.load(response)
status,session=call('/api/sessions',{'title':task['title'],'source':'desktop','model':task['model']})
sid=session['id']
print(json.dumps({'event':'session_created','status':status,'session_id':sid,'recorded_at':time.time()}),flush=True)
started=time.time()
try:
 status,response=call('/v1/chat/completions',{'model':task['model'],'messages':[{'role':'user','content':task['prompt']}],'stream':False},{'X-Hermes-Session-Id':sid})
 print(json.dumps({'event':'task_response','status':status,'session_id':sid,'elapsed_seconds':time.time()-started,'response':response}),flush=True)
except Exception as error:
 print(json.dumps({'event':'request_error','session_id':sid,'error_type':type(error).__name__,'elapsed_seconds':time.time()-started}),flush=True)
 raise SystemExit(1)
'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--guest', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--model', required=True, help='An ID verified in the installed bridge model catalog')
    parser.add_argument('--title', default='阅读采购预算：执行与记忆')
    parser.add_argument('--prompt', help='Override with another public demonstration task')
    args = parser.parse_args()
    if args.output.exists():
        parser.error('Output exists; inspect the previous session before retrying')
    task = {'title': args.title, 'model': args.model, 'prompt': args.prompt or (
        '这是公开合成演示任务。请先用系统终端工具计算科普书33元、工具书39元、画册28元的总额，'
        '用文件写入工具把中文核对结果分四行写入 /tmp/pixiu-阅读预算.txt，使用真正的换行；然后读取文件确认结果。'
        '再调用 web_search 工具查找 openKylin 官方网站，依据真实搜索结果给出官网链接。'
        '最后调用 pixiu_memory_remember 记住“家庭阅读采购预算：科普书33元、工具书39元、画册28元，合计100元”，'
        '作为后续核对依据。最终用中文简短说明实际完成的步骤，不要仅描述计划。')}
    report = {'environment': 'V11虚拟机已安装Agent网关；公开合成任务', 'request': task,
              'status': 'in_progress', 'events': []}

    def save():
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')

    save()
    process = subprocess.Popen(['ssh', '-o', 'BatchMode=yes', args.guest,
                                'python3 -c ' + shlex.quote(REMOTE)], stdin=subprocess.PIPE,
                               stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    process.stdin.write(json.dumps(task))
    process.stdin.close()
    for line in process.stdout:
        try:
            event = json.loads(line)
        except json.JSONDecodeError:
            continue  # Guest login banners are not gateway evidence.
        report['events'].append(event)
        save()
        print(event['event'], event.get('session_id', ''), flush=True)
    code = process.wait()
    report['status'] = 'response_received' if code == 0 else 'request_failed'
    report['ssh_exit_code'] = code
    save()
    raise SystemExit(code)


if __name__ == '__main__':
    main()
