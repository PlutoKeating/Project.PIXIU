from pathlib import Path
import json,subprocess
from PIL import Image,ImageDraw,ImageFont
p=Path('submission/video-production'); out=p/'review/independent-full-22'; dst=out/'frames'; dst.mkdir(exist_ok=True)
t=json.load(open(p/'review/source-snapshots/full-draft-22/src/timeline.json'))
frames=set()
for s in t['shots']:
 for off in [0,20,60,int(s['duration']*.35),int(s['duration']*.65),s['duration']-20]:frames.add(s['from']+off)
 if s['motion'] not in ['live','diagram','metrics']:
  for off in [8,16,32,48,80,100,130,150,180,200]:
   if off<s['duration']:frames.add(s['from']+off)
for s in t['shots'][1:]:frames.add(s['from']-1)
fs=sorted(frames); json.dump({'fps':t['fps'],'frames':fs,'method':'ffmpeg select eq(n, global zero-based frame)','shots':t['shots']},open(out/'sampling.json','w'),ensure_ascii=False,indent=2)
subprocess.run(['ffmpeg','-hide_banner','-loglevel','error','-i',str(p/'renders/全片初剪-22.mp4'),'-vf','select='+ '+'.join('eq(n\\,%d)'%f for f in fs),'-vsync','0','-q:v','2',str(dst/'x%04d.jpg')],check=True)
for i,f in enumerate(fs): (dst/('x%04d.jpg'%(i+1))).rename(dst/('f%05d.jpg'%f))
font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',20)
for s in t['shots']:
 sf=[f for f in fs if s['from']<=f<s['from']+s['duration']]
 sheet=Image.new('RGB',(1920,384*((len(sf)+2)//3)), 'white'); d=ImageDraw.Draw(sheet)
 for i,f in enumerate(sf):
  im=Image.open(dst/('f%05d.jpg'%f)); im.thumbnail((640,360)); x=i%3*640;y=i//3*384;sheet.paste(im,(x,y));d.text((x+5,y+360),s['id']+' global f'+str(f)+' local '+str(f-s['from']),fill='black',font=font)
 sheet.save(out/(s['id']+'-sheet.jpg'),quality=92)
print('extracted',len(fs),'frames; 30 shot sheets')
