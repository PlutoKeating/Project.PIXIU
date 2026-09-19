"""Bind the deck reference frames to the actual delivered promotional film."""
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import hashlib,json,subprocess
from PIL import Image,ImageDraw
R=Path(__file__).resolve().parents[3];W=R/'submission/presentation-production';V=R/'submission/video-production'
p=V/'renders/演示视频-0.1.12演示增强版.mp4';meta=json.loads((V/'review/directed-final-package.json').read_text())
assert hashlib.sha256(p.read_bytes()).hexdigest()==meta['video_sha256']
t=json.loads((V/'src/timeline.json').read_text());out=W/'assets/video-frames';out.mkdir(exist_ok=True)
jobs=[]
for s in t['shots']:
 for phase in [.35,.72]:
  f=round(s['from']+phase*s['duration']);target=out/f"{s['id']}-{int(phase*100)}.png";jobs.append((s['id'],f,target))
def extract(j):
 sid,f,target=j
 subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-y','-ss',str(f/30),'-i',str(p),'-map','0:v:0','-frames:v','1',str(target)],check=True)
 return {'shot':sid,'frame':f,'seconds':f/30,'path':target.relative_to(R).as_posix(),'sha256':hashlib.sha256(target.read_bytes()).hexdigest()}
with ThreadPoolExecutor(max_workers=4) as pool:frames=list(pool.map(extract,jobs))
for start in range(0,len(frames),4):
 canvas=Image.new('RGB',(1920,1120),'#eaf2ff');d=ImageDraw.Draw(canvas)
 for k,r in enumerate(frames[start:start+4]):
  im=Image.open(R/r['path']);im.thumbnail((960,540));x=(k%2)*960;y=(k//2)*560;canvas.paste(im,(x,y+20));d.text((x+8,y+3),f"{r['shot']} / frame {r['frame']} / {r['seconds']:.2f}s",fill='black')
 canvas.save(W/f'review/video-aligned/reference-{start//4+1:02}.png')
(W/'review/video-aligned/video-reference.json').write_text(json.dumps({'video':p.relative_to(R).as_posix(),'video_sha256':meta['video_sha256'],'duration_seconds':t['seconds'],'frames':frames},ensure_ascii=False,indent=2)+'\n')
print('Verified delivered film; extracted 60 frames across all 30 shots.')
