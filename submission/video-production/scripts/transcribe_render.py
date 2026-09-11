#!/usr/bin/env python3
"""Read back a rendered soundtrack with Azure recognition and preserve timings."""
import argparse
import getpass
import hashlib
import json
import os
from pathlib import Path
import subprocess
import threading
import time
import uuid

import azure.cognitiveservices.speech as sdk

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--video', required=True, type=Path)
    parser.add_argument('--output', required=True, type=Path)
    parser.add_argument('--region', default=os.environ.get('SPEECH_REGION'))
    parser.add_argument('--start', type=float, default=0)
    args = parser.parse_args()
    if args.output.exists() or not args.region:
        parser.error('Provide a region and a new output path')
    wav = ROOT / '.runtime' / ('readback-' + uuid.uuid4().hex + '.wav')
    subprocess.run(['ffmpeg', '-v', 'error', '-ss', str(args.start), '-i', str(args.video),
                    '-vn', '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', str(wav)], check=True)
    key = os.environ.get('SPEECH_KEY') or getpass.getpass('Speech key (hidden, memory only): ')
    config = sdk.SpeechConfig(subscription=key, region=args.region)
    config.speech_recognition_language = 'zh-CN'
    config.output_format = sdk.OutputFormat.Detailed
    recognizer = sdk.SpeechRecognizer(speech_config=config, audio_config=sdk.audio.AudioConfig(filename=str(wav)))
    rows, events = [], []
    done = threading.Event()

    def recognized(event):
        if event.result.reason == sdk.ResultReason.RecognizedSpeech:
            rows.append({'text': event.result.text,
                         'offset_seconds': args.start + event.result.offset / 1e7,
                         'duration_seconds': event.result.duration / 1e7})

    def canceled(event):
        events.append({'reason': str(event.reason), 'error_code': str(event.error_code)})
        done.set()

    recognizer.recognized.connect(recognized)
    recognizer.canceled.connect(canceled)
    recognizer.session_stopped.connect(lambda _: done.set())
    began = time.monotonic()
    try:
        recognizer.start_continuous_recognition_async().get()
        while not done.wait(20):
            print('Recognized segments:', len(rows), flush=True)
            if time.monotonic() - began > 1200:
                events.append({'reason': 'review timeout'})
                break
        recognizer.stop_continuous_recognition_async().get()
        args.output.write_text(json.dumps({
            'method': 'Azure zh-CN recognition of decoded rendered soundtrack',
            'video_sha256': hashlib.sha256(args.video.read_bytes()).hexdigest(),
            'start_seconds': args.start, 'segments': rows, 'events': events,
            'elapsed_seconds': time.monotonic() - began,
        }, ensure_ascii=False, indent=2) + '\n')
        print('Readback saved:', len(rows), 'segments', flush=True)
    finally:
        key = None
        wav.unlink(missing_ok=True)


if __name__ == '__main__':
    main()
