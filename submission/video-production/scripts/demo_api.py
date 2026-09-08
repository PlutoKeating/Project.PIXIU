#!/usr/bin/env python3
"""Call the installed guest's loopback API via SSH; keep tokens off command lines."""
import json
import shlex
import subprocess

REMOTE = '''import json,sys,urllib.request,urllib.error
request=json.load(sys.stdin)
data=request.get("data")
req=urllib.request.Request("http://127.0.0.1:8765"+request["path"],
 data=None if data is None else json.dumps(data).encode(),
 headers={"Content-Type":"application/json"})
try:
 with urllib.request.urlopen(req,timeout=90) as response:
  print(json.dumps({"status":response.status,"body":json.load(response)}))
except urllib.error.HTTPError as error:
 print(json.dumps({"status":error.code,"body":json.load(error)}))
'''


def call(guest, path, data=None):
    result = subprocess.run(
        ['ssh', '-o', 'BatchMode=yes', guest, 'python3 -c ' + shlex.quote(REMOTE)],
        input=json.dumps({'path': path, 'data': data}), text=True,
        capture_output=True, timeout=100, check=True,
    )
    return json.loads(result.stdout)


def pair_all(guests):
    """Establish mutual trust using fresh single-use QR tokens, never persisted."""
    results = []
    for source in guests:
        for target in guests:
            if source == target:
                continue
            token = call(source, '/sync/token', {'method': 'QR', 'ttl_seconds': 300})
            if token['status'] != 200:
                raise RuntimeError('Token creation failed')
            paired = call(target, '/sync/pair', {'method': 'QR', 'token': token['body']['token']})
            if paired['status'] != 200:
                raise RuntimeError('Pairing failed: ' + str(paired['status']))
            results.append(paired['body'])
    return results
