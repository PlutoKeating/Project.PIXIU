#!/usr/bin/env python3
"""Run inside a capture guest; isolate demo storage and start installed backend.

Requires ca.crt, device.crt and device.key in ~/.local/state/pixiu-video/tls.
Does not edit the installed service or the user's normal PIXIU configuration.
Stop pixiu-video-backend and start pixiu-backend to restore normal backend use.
"""
import argparse
from pathlib import Path
import secrets
import shlex
import subprocess

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--device', choices=['a', 'b', 'c'], required=True)
parser.add_argument('--address', required=True)
args = parser.parse_args()
root = Path.home() / '.local/state/pixiu-video'
root.mkdir(mode=0o700, parents=True, exist_ok=True)
envfile = root / 'backend.env'
if envfile.exists():
    raise SystemExit('Demo configuration exists; inspect or restart the existing unit')
names = {'a': '书房工作站', 'b': '随身笔记本', 'c': '客厅一体机'}
env = {
    'PYTHONPATH': '/usr/lib/pixiu',
    'PIXIU_PRODUCT_VERSION': '0.1.9',
    'PIXIU_DB_PATH': str(root / 'pixiu.db'),
    'PIXIU_DATA_DIR': str(root / 'data'),
    'PIXIU_VECTOR_DB_PATH': str(root / 'vector-engine.db'),
    'PIXIU_EMBEDDING': 'kylin', 'PIXIU_VECTOR_STORE': 'kylin',
    'PIXIU_VECTOR_APP_ID': 'pixiu_video_' + args.device,
    'PIXIU_VECTOR_COLLECTION': 'demo_memory',
    'PIXIU_SYNC_NETWORK_ENABLED': 'true',
    'PIXIU_SYNC_DEVICE_NAME': names[args.device],
    'PIXIU_SYNC_DOMAIN': 'shared:home',
    'PIXIU_SYNC_KEY_PASSPHRASE': secrets.token_urlsafe(32),
    'PIXIU_SYNC_BIND_HOST': args.address,
    'PIXIU_SYNC_PORT': '8766',
    'PIXIU_SYNC_SERVER_NAME': 'pixiu-video-' + args.device,
    'PIXIU_SYNC_ADVERTISE_ADDRESSES': args.address,
    'PIXIU_SYNC_CERTFILE': str(root / 'tls/device.crt'),
    'PIXIU_SYNC_KEYFILE': str(root / 'tls/device.key'),
    'PIXIU_SYNC_CAFILE': str(root / 'tls/ca.crt'),
    'PIXIU_MONITOR_ENABLED': 'false',
}
for filename in ('ca.crt', 'device.crt', 'device.key'):
    if not (root / 'tls' / filename).is_file():
        raise SystemExit('Missing demo TLS file: ' + filename)
envfile.touch(mode=0o600)
envfile.write_text(''.join(k + '=' + shlex.quote(v) + '\n' for k, v in env.items()))
subprocess.run(['systemctl', '--user', 'stop', 'pixiu-backend.service'], check=True)
subprocess.run([
    'systemd-run', '--user', '--unit=pixiu-video-backend',
    '--property=EnvironmentFile=' + str(envfile),
    '--property=Restart=on-failure',
    '/usr/lib/pixiu/venv/bin/python', '-m', 'uvicorn',
    'backend.foundation.api.http_app:app', '--host', '127.0.0.1', '--port', '8765',
], check=True)
print(names[args.device] + '：已启动隔离演示服务')
