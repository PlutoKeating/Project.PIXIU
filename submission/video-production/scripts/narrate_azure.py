#!/usr/bin/env python3
"""Resumable Azure narration. Credentials are read hidden and retained only in memory."""
import argparse
import getpass
import hashlib
import json
from pathlib import Path
import subprocess
import time
from xml.sax.saxutils import escape
import azure.cognitiveservices.speech as sdk

ROOT = Path(__file__).resolve().parents[1]

def digest(data):
    return hashlib.sha256(data).hexdigest()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--shots', nargs='+')
    parser.add_argument('--region', required=True)
    parser.add_argument('--phrase', help='Synthesize only this short replacement phrase')
    parser.add_argument('--phrase-id', help='New asset folder for the replacement phrase')
    args = parser.parse_args()
    if args.phrase and (args.shots or not args.phrase_id or not args.phrase_id.replace('-', '').isalnum()):
        parser.error('A phrase requires a safe phrase-id and cannot be combined with shots')
    settings = json.loads((ROOT / 'storyboard/narration.json').read_text())
    shots = json.loads((ROOT / 'storyboard/shots.json').read_text())['shots']
    if args.shots:
        assert set(args.shots) <= {s['id'] for s in shots}
        shots = [s for s in shots if s['id'] in args.shots]
    if args.phrase:
        shots = [{'id': args.phrase_id, 'narration': args.phrase}]
    key = getpass.getpass('Speech key (hidden, memory only): ')
    config = sdk.SpeechConfig(subscription=key, region=args.region)
    config.set_speech_synthesis_output_format(sdk.SpeechSynthesisOutputFormat.Audio24Khz96KBitRateMonoMp3)
    config.set_property(sdk.PropertyId.SpeechServiceResponse_RequestWordBoundary, 'true')
    # One request at a time; successful assets are never regenerated.
    for shot in shots:
        if shot.get('audio_reuse'):
            print(f"{shot['id']}: reuses {shot['audio_reuse']}; synthesis skipped", flush=True)
            continue
        request = {'text': shot['narration'], **settings}
        request_hash = digest(json.dumps(request, ensure_ascii=False, sort_keys=True).encode())
        folder = ROOT / 'raw/audio' / shot['id']
        folder.mkdir(parents=True, exist_ok=True)
        audio = folder / (request_hash[:12] + '.mp3')
        meta = audio.with_suffix('.json')
        if audio.exists() and meta.exists():
            old = json.loads(meta.read_text())
            if old['request_sha256'] == request_hash and old['audio_sha256'] == digest(audio.read_bytes()):
                print(shot['id'], 'reused', flush=True)
                continue
        boundaries = []
        synth = sdk.SpeechSynthesizer(speech_config=config, audio_config=None)
        def on_word(event):
            if event.boundary_type == sdk.SpeechSynthesisBoundaryType.Word:
                boundaries.append({'offset': event.audio_offset,
                                   'duration': round(event.duration.total_seconds() * 1e7),
                                   'text': event.text})
        synth.synthesis_word_boundary.connect(on_word)
        ssml = ('<speak version="1.0" xmlns="http://www.w3.org/2001/10/synthesis" xml:lang="zh-CN">'
                f'<voice name="{settings["voice"]}"><prosody rate="{settings["rate"]}">'
                + escape(shot['narration']) + '</prosody></voice></speak>')
        for attempt in range(3):
            result = synth.speak_ssml_async(ssml).get()
            if result.reason == sdk.ResultReason.SynthesizingAudioCompleted:
                break
            code = result.cancellation_details.error_code
            print(shot['id'], 'attempt', attempt + 1, str(code), flush=True)
            if code in (sdk.CancellationErrorCode.AuthenticationFailure, sdk.CancellationErrorCode.Forbidden, sdk.CancellationErrorCode.BadRequest):
                break
            boundaries.clear()
            time.sleep(2)
        if result.reason != sdk.ResultReason.SynthesizingAudioCompleted:
            # SDK cancellation details can include request information: do not log them.
            raise RuntimeError(f'{shot["id"]}: synthesis failed ({result.reason}); stopped without retry')
        assert result.audio_data and boundaries, 'Audio or word boundaries missing'
        partial = audio.with_suffix('.partial')
        partial.write_bytes(result.audio_data)
        subprocess.run(['ffmpeg', '-v', 'error', '-i', str(partial), '-f', 'null', '-'], check=True, capture_output=True)
        seconds = float(subprocess.check_output(['ffprobe', '-v', 'error', '-show_entries', 'format=duration',
                         '-of', 'default=noprint_wrappers=1:nokey=1', str(partial)]))
        partial.replace(audio)
        meta.write_text(json.dumps({'shot': shot['id'], 'request': request, 'request_sha256': request_hash,
            'audio_sha256': digest(audio.read_bytes()), 'duration_seconds': seconds,
            'boundary_unit': '100 nanoseconds', 'boundaries': boundaries, 'sdk_version': sdk.__version__,
            'status': 'Azure original narration; word boundaries preserved'}, ensure_ascii=False, indent=2) + '\n')
        print(shot['id'], f'{seconds:.3f}s', len(boundaries), 'words', flush=True)
    key = None

if __name__ == '__main__':
    main()
