#!/usr/bin/env python3
"""Generate resumable Chinese narration and measured word boundaries.

Only public storyboard text is sent to the speech service. Original audio and
service timings are preserved; changed text/voice is never silently reused.
"""
import argparse
import asyncio
import hashlib
import json
from pathlib import Path
import subprocess

import edge_tts

ROOT = Path(__file__).resolve().parents[1]


async def generate(shot, voice, rate):
    folder = ROOT / 'raw' / 'audio' / shot['id']
    folder.mkdir(parents=True, exist_ok=True)
    request = {'text': shot['narration'], 'voice': voice, 'rate': rate}
    key = hashlib.sha256(json.dumps(request, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    audio = folder / f'{key[:12]}.mp3'
    metadata = folder / f'{key[:12]}.json'
    if audio.exists() and metadata.exists():
        previous = json.loads(metadata.read_text())
        if previous['request_sha256'] == key and previous['audio_sha256'] == hashlib.sha256(audio.read_bytes()).hexdigest():
            print(shot['id'], '已存在并核对摘要', flush=True)
            return
    partial = audio.with_suffix('.partial')
    boundaries = []
    try:
        with partial.open('wb') as output:
            async for chunk in edge_tts.Communicate(request['text'], voice, rate=rate, boundary='WordBoundary').stream():
                if chunk['type'] == 'audio':
                    output.write(chunk['data'])
                elif chunk['type'] == 'WordBoundary':
                    boundaries.append({k: chunk[k] for k in ('offset', 'duration', 'text')})
        if not boundaries or partial.stat().st_size == 0:
            raise RuntimeError('语音或对齐信息为空')
        duration = float(subprocess.check_output([
            'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
            '-of', 'default=noprint_wrappers=1:nokey=1', str(partial)], text=True))
        partial.replace(audio)
        metadata.write_text(json.dumps({
            'shot': shot['id'], 'request': request, 'request_sha256': key,
            'audio_sha256': hashlib.sha256(audio.read_bytes()).hexdigest(),
            'duration_seconds': duration, 'boundary_unit': '100 nanoseconds',
            'boundaries': boundaries, 'status': '原始合成音，待试听及字幕校准',
        }, ensure_ascii=False, indent=2) + '\n')
        print(shot['id'], f'{duration:.3f} 秒', flush=True)
    finally:
        partial.unlink(missing_ok=True)


async def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--shots', nargs='+', required=True, help='明确选择镜头 ID，如 s01 s02')
    parser.add_argument('--voice', default='zh-CN-YunxiNeural')
    parser.add_argument('--rate', default='-5%')
    args = parser.parse_args()
    shots = json.loads((ROOT / 'storyboard/shots.json').read_text())['shots']
    available = {shot['id']: shot for shot in shots}
    unknown = set(args.shots) - available.keys()
    if unknown:
        parser.error('未知镜头：' + ', '.join(sorted(unknown)))
    for shot_id in args.shots:
        await generate(available[shot_id], args.voice, args.rate)


if __name__ == '__main__':
    asyncio.run(main())
