#!/usr/bin/env python3
"""Record a real V11 desktop and timestamp QEMU pointer actions at native speed.

Run on the libvirt host. Guest dependencies: FFmpeg and an active Xwayland
display. The compositor pointer is already present in x11grab pixels, so
draw_mouse=0 avoids drawing a second pointer. Plans contain public demo actions.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import threading
import time
import uuid

import libvirt
import libvirt_qemu


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--guest', required=True)
    parser.add_argument('--domain', required=True)
    parser.add_argument('--plan', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text())
    if args.output.exists():
        parser.error('Choose a new recording path')
    args.output.parent.mkdir(parents=True, exist_ok=True)
    connection = libvirt.open('qemu:///system')
    domain = connection.lookupByName(args.domain)
    width, height = plan.get('size', [1440, 900])
    remote = '/tmp/pixiu-directed-' + uuid.uuid4().hex + '.mp4'
    duration = plan['duration']
    command = ['ffmpeg', '-nostdin', '-v', 'error', '-f', 'x11grab',
               '-draw_mouse', '0', '-framerate', '30', '-video_size', f'{width}x{height}',
               '-i', ':0', '-t', str(duration), '-c:v', 'libx264', '-preset', 'ultrafast',
               '-crf', '18', '-pix_fmt', 'yuv420p', '-progress', 'pipe:1',
               '-stats_period', '0.2', remote]
    if plan.get('redact_rectangles'):
        filters = [f'drawbox=x={x}:y={y}:w={w}:h={h}:color=0xe8eef5:t=fill'
                   for x, y, w, h in plan['redact_rectangles']]
        command[-1:-1] = ['-vf', ','.join(filters)]
    recording = subprocess.Popen(['ssh', '-o', 'BatchMode=yes', args.guest,
                                 shlex.join(command)], stdout=subprocess.PIPE, text=True)
    source_time = 0
    while True:
        line = recording.stdout.readline()
        if not line:
            raise RuntimeError('FFmpeg did not report its first frame')
        if line.startswith('out_time_us=') and line.strip().split('=')[1] != 'N/A':
            source_time = int(line.strip().split('=')[1]) / 1e6
        if line.startswith('progress='):
            break
    start = time.monotonic() - source_time
    def drain_progress():
        for _ in recording.stdout:
            pass
    progress_thread = threading.Thread(target=drain_progress, daemon=True)
    progress_thread.start()
    records = []
    position = plan.get('pointer_start', [500, 400])

    def event(events):
        response = json.loads(libvirt_qemu.qemuMonitorCommand(domain, json.dumps({
            'execute': 'input-send-event', 'arguments': {'events': events}}), 0))
        if 'error' in response:
            raise RuntimeError(response['error'])

    def move(x, y):
        event([{'type': 'abs', 'data': {'axis': axis, 'value': round(value / (size - 1) * 32767)}}
               for axis, value, size in [('x', x, width), ('y', y, height)]])

    def wait_until(seconds):
        time.sleep(max(0, start + seconds - time.monotonic()))

    try:
        for action in plan['actions']:
            wait_until(action['at'])
            began = time.monotonic() - start
            target = action.get('to', position)
            travel = action.get('travel', 0.8)
            steps = max(1, round(travel * 60))
            for index in range(steps + 1):
                t = index / steps
                eased = 4*t*t*t if t < .5 else 1 - (-2*t + 2)**3 / 2
                # A small arc gives a natural, readable approach to the control.
                bend = action.get('arc', 22) * 4 * eased * (1 - eased)
                move(position[0] + (target[0] - position[0]) * eased,
                     position[1] + (target[1] - position[1]) * eased + bend)
                wait_until(began + index * travel / steps)
            position = target
            clicked = None
            if action.get('click'):
                time.sleep(.12)
                clicked = time.monotonic() - start
                event([{'type': 'btn', 'data': {'down': True, 'button': 'left'}}])
                time.sleep(.09)
                event([{'type': 'btn', 'data': {'down': False, 'button': 'left'}}])
            if 'text' in action or 'text_env' in action:
                # Keep the guest clipboard in memory and restore it after paste.
                code = '''import json,os,subprocess,sys,time
text=json.load(sys.stdin)['text']
env={**os.environ,'DISPLAY':':0','XDG_RUNTIME_DIR':'/run/user/1000','WAYLAND_DISPLAY':'wayland-0'}
old=subprocess.run(['wl-paste','--no-newline'],env=env,capture_output=True)
subprocess.run(['wl-copy'],input=text.encode(),env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True)
time.sleep(2)
subprocess.run(['xdotool','key','ctrl+a','ctrl+v'],env=env,check=True)
time.sleep(3)
subprocess.run(['wl-copy'],input=old.stdout if old.returncode==0 else b'',env=env,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,check=True)
'''
                subprocess.run(['ssh', '-o', 'BatchMode=yes', args.guest,
                                'python3 -c ' + shlex.quote(code)],
                               input=json.dumps({'text': os.environ[action['text_env']] if 'text_env' in action else action['text']}).encode(), check=True)
            if action.get('escape'):
                event([{'type':'key','data':{'down':True,'key':{'type':'qcode','data':'esc'}}}])
                event([{'type':'key','data':{'down':False,'key':{'type':'qcode','data':'esc'}}}])
            records.append({**action, 'actual_start': began, 'actual_click': clicked,
                            'actual_end': time.monotonic() - start})
        recording.wait(timeout=max(30, duration - (time.monotonic() - start) + 30))
        if recording.returncode:
            raise RuntimeError('Desktop recording failed')
        subprocess.run(['scp', '-q', args.guest + ':' + remote, str(args.output)], check=True)
        subprocess.run(['ssh', args.guest, 'rm', '--', remote], check=True)
        subprocess.run(['ffmpeg', '-v', 'error', '-i', str(args.output), '-f', 'null', '-'], check=True)
        metadata = {'version': '0.1.12', 'platform': '银河麒麟 V11', 'capture_fps': 30,
                    'timing_basis': 'FFmpeg first progress packet, aligned to output timestamp',
                    'size': [width, height], 'redact_rectangles': plan.get('redact_rectangles', []),
                    'pointer': 'native compositor pointer; QEMU input events',
                    'data': '公开合成演示资料', 'actions': records,
                    'sha256': hashlib.sha256(args.output.read_bytes()).hexdigest()}
        args.output.with_suffix('.json').write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + '\n')
    finally:
        if recording.poll() is None:
            recording.terminate()
            recording.wait(timeout=10)
        connection.close()


if __name__ == '__main__':
    main()
