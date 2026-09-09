#!/usr/bin/env python3
"""Raise narration independently of SFX, reuse approved pictures and prepared music."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import numpy as np
from measure_audio_sync import decode, measure

parser=argparse.ArgumentParser(description=__doc__)
parser.add_argument('--baseline',type=Path,required=True,help='Approved no-BGM export with original 1x narration')
parser.add_argument('--output',type=Path,required=True)
parser.add_argument('--no-bgm',type=Path,required=True)
parser.add_argument('--report',type=Path,required=True)
parser.add_argument('--reuse-no-bgm',action='store_true',help='Resume after this script already exported the no-music variant')
a=parser.parse_args()
assert not a.no_bgm.exists() or a.reuse_no_bgm
assert not any(p.exists() for p in (a.output,a.report)), 'Preserve previous exports'
t=json.loads(Path('src/timeline.json').read_text())
v=json.loads(Path('src/narration-volume.json').read_text())
b=json.loads(Path('src/bgm.json').read_text())
rate=48000; duration=t['duration']/t['fps']; count=round(duration*rate)
def ff(*args): return subprocess.check_output(['ffmpeg','-v','error','-nostdin',*map(str,args)])
def stereo(path): return np.frombuffer(ff('-i',path,'-ac',2,'-ar',rate,'-f','f32le','-'),dtype='<f4').reshape(-1,2)
def padded(x):
 out=np.zeros((count,2),dtype=np.float32);out[:min(count,len(x))]=x[:count];return out
original=padded(stereo(a.baseline)); mono=original.mean(axis=1).astype(np.float64)
extra=np.zeros_like(original); rows=[]
folder=Path('public')/v['prepared_directory'];folder.mkdir(parents=True,exist_ok=True)
for shot in t['shots']:
 source=Path('public')/shot['audio']
 raw=decode(source)
 probe_offset=0
 probe=raw[:min(len(raw),rate*3)]
 found=measure(mono,probe,shot['from']+shot['audio_from'])
 if found['normalized_correlation'] < .98:
  # The outro impact overlaps the opening phrase; use a later clean phrase.
  for seconds in (1,2,3,4):
   candidate=raw[seconds*rate:(seconds+3)*rate]
   if len(candidate)<rate: continue
   trial=measure(mono,candidate,shot['from']+shot['audio_from']+seconds*t['fps'])
   if trial['normalized_correlation']>found['normalized_correlation']:
    probe_offset=seconds*rate; probe=candidate; found=trial
 assert found['normalized_correlation']>.98 and abs(found['pipeline_offset_frames'])<1, (shot['id'],found)
 start=round(found['measured_start_frame']*rate/t['fps'])-probe_offset
 found['probe_offset_seconds']=probe_offset/rate
 found['measured_start_frame']=start*t['fps']/rate
 # Clip at the same scene boundary as the source Sequence (plus measured pipeline offset).
 end=min(count,round((shot['from']+shot['duration']+1.28)*rate/t['fps']),start+len(raw))
 coeff=(probe@original[start+probe_offset:start+probe_offset+len(probe)])/(probe@probe)
 assert np.all(abs(coeff-2**-.5)<.015), 'Unexpected original channel gain'
 extra[start:end]+=(raw[:end-start,None]*coeff[None,:]*(v['gain']-1)).astype(np.float32)
 prepared=folder/(source.stem+'.wav')
 # Stereo conversion matches original mono-to-stereo mixing, with safe PCM headroom.
 if not prepared.exists():
  ff('-i',source,'-af',f'aformat=sample_rates=48000:channel_layouts=stereo,volume={v["gain"]}', '-c:a','pcm_s16le',prepared)
 row={'shot':shot['id'],**found,'original_channel_gain':coeff.tolist(),'prepared_sha256':hashlib.sha256(prepared.read_bytes()).hexdigest()}
 rows.append(row)
voice_mix=original+extra
music=padded(stereo(Path('public')/b['prepared']))
final=voice_mix+music*b['volume']
peaks={}
for label,out,pcm in [('no_bgm',a.no_bgm,voice_mix),('bgm',a.output,final)]:
 peak=float(abs(pcm).max())
 limit=peak>=1
 filters=['-af','alimiter=limit=0.98:level=false:latency=true'] if limit else []
 temp=Path('.runtime')/(out.stem+'.f32');temp.parent.mkdir(exist_ok=True)
 pcm.astype('<f4').tofile(temp)
 if not out.exists():
  ff('-i',a.baseline,'-f','f32le','-ar',rate,'-ac',2,'-i',temp,'-map','0:v:0','-map','1:a:0',*filters,'-c:v','copy','-c:a','aac','-b:a','320k','-t',duration,'-movflags','+faststart',out)
 temp.unlink()
 ff('-i',out,'-f','null','-')
 enc_peak=float(abs(stereo(out)).max());assert enc_peak<1
 peaks[label]={'linear_peak_dbfs':float(20*np.log10(peak)),'encoded_peak_dbfs':float(20*np.log10(enc_peak)), 'peak_limiter':limit, 'limiter_ceiling':.98 if limit else None, 'samples_above_full_scale':int(np.count_nonzero(abs(pcm)>=1))}
 print(label,peaks[label],flush=True)
def picture(path):return ff('-i',path,'-map','0:v:0','-c','copy','-f','hash','-hash','sha256','-').decode().strip()
assert picture(a.output)==picture(a.no_bgm)==picture(a.baseline)
report={'sha256':hashlib.sha256(a.output.read_bytes()).hexdigest(),'complete_decode':'passed','baseline':str(a.baseline),'baseline_sha256':hashlib.sha256(a.baseline.read_bytes()).hexdigest(),'narration_gain':v['gain'],'music_gain':b['volume'],'duration_seconds':duration,'picture_bitstream_unchanged':True,'peaks':peaks,'narration_alignment':rows,'method':f'Add {v["gain"]-1:g}x source narration at measured original sample positions and channel gains to the approved 1x no-music track. Existing SFX retained; add prepared music at {b["volume"]:g}x. No normalization, ducking, timing or speed changes. If full scale is exceeded, apply a latency-compensated 0.98 peak limiter with auto-level disabled.'}
a.report.write_text(json.dumps(report,ensure_ascii=False,indent=2)+'\n')
