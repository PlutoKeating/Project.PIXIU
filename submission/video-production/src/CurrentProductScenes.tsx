import React from 'react';
import {AbsoluteFill, Img, OffthreadVideo, Sequence, interpolate, staticFile, useCurrentFrame} from 'remotion';
import data from './current-scenes.json';
import story from '../storyboard/shots.json';
import {Fonts} from './Fonts';

type Asset = {kind: string; src: string; end?: string; width: number; height: number; frames?: number; playback_alignment?: string};
type Segment = {asset: string; label: string; cue: string | null; fraction: number};
type SceneShot = {id: string; duration: number; captions?: {text: string; from: number}[]};
const assets: Record<string, Asset> = data.assets;
const scenes: Record<string, Segment[]> = data.scenes;
export const hasCurrentScene = (id: string) => Boolean(scenes[id]);

const Media: React.FC<{asset: Asset; duration: number}> = ({asset, duration}) => {
  const f = useCurrentFrame();
  const playbackFrames = Math.min(asset.frames ?? 0, Math.max(1, duration - 18));
  const trimBefore = asset.playback_alignment === 'start' ? 0 : Math.max(0, (asset.frames ?? 0) - playbackFrames);
  const scale = Math.min(1580 / asset.width, 660 / asset.height, asset.width < 300 ? 3.2 : 2.2);
  const w = asset.width * scale, h = asset.height * scale;
  const enter = asset.kind === 'video' ? 1 : interpolate(f, [0, 16], [0, 1], {extrapolateRight:'clamp'});
  const style = {width:w, height:h, display:'block'};
  return <div style={{position:'absolute',left:(1920-w)/2,top:175+(660-h)/2,
    overflow:'hidden',borderRadius:12,background:'#fff',boxShadow:'0 16px 45px #17203318',
    opacity:enter,transform:`perspective(1600px) translateY(${18*(1-enter)}px) rotateX(${3*(1-enter)}deg)`}}>
    {asset.kind==='video' && f<playbackFrames
      ? <OffthreadVideo src={staticFile(asset.src)} trimBefore={trimBefore} muted style={style}/>
      : <Img src={staticFile(asset.kind==='video' ? asset.end! : asset.src)} style={style}/>}
  </div>;
};

export const CurrentProductScene: React.FC<{shot:SceneShot}> = ({shot}) => {
  const f=useCurrentFrame();
  const rows=scenes[shot.id];
  const starts=rows.map(row => row.cue
    ? (shot.captions?.find(c=>c.text.includes(row.cue!))?.from ?? Math.round(row.fraction*shot.duration))
    : 0);
  const index=starts.reduce((selected,at,i)=>f>=at?i:selected,0);
  return <>
    {rows.map((row,i)=><Sequence key={row.asset+i} from={starts[i]}
      durationInFrames={Math.max(1,(starts[i+1]??shot.duration)-starts[i])}>
      <Media asset={assets[row.asset]} duration={Math.max(1,(starts[i+1]??shot.duration)-starts[i])}/>
    </Sequence>)}
    <div style={{position:'absolute',top:866,left:140,right:140,color:'#1456b8',fontSize:35,
      fontWeight:700,textAlign:'center'}}>{rows[index].label}</div>
    <div style={{position:'absolute',top:922,left:140,right:140,color:'#526477',fontSize:22,
      textAlign:'center'}}>PIXIU 0.1.12 · 银河麒麟 V11 实拍 · 公开合成资料</div>
  </>;
};

const reviewShots=story.shots.filter(s=>hasCurrentScene(s.id));
let reviewCursor=0;
const reviewTimeline=reviewShots.map(shot=>{
  const row={...shot,from:reviewCursor,duration:shot.planned_duration_seconds*30};
  reviewCursor+=row.duration;
  return row;
});
export const CURRENT_REVIEW_DURATION=reviewCursor;
export const CurrentMaterialsReview: React.FC=()=> <AbsoluteFill style={{background:'#f6f7f9',
  color:'#172033',fontFamily:'"Noto Sans CJK SC",sans-serif'}}><Fonts/>
  {reviewTimeline.map(shot=><Sequence key={shot.id} from={shot.from} durationInFrames={shot.duration}>
    <div style={{position:'absolute',top:58,left:135,fontSize:45,fontWeight:700}}>{shot.title}</div>
    <CurrentProductScene shot={{id:shot.id,duration:shot.duration}}/>
    <div style={{position:'absolute',top:20,right:35,fontSize:20,color:'#526477'}}>新版画面审阅 · {shot.id}</div>
  </Sequence>)}
</AbsoluteFill>;
