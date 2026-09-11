import React from 'react';
import {AbsoluteFill, Easing, Img, OffthreadVideo, Sequence, interpolate, staticFile, useCurrentFrame} from 'remotion';
import data from './directed-scenes.json';

type Asset = {kind: string; src: string; end?: string; width: number; height: number;
  result_asset?: string; result_from?: number; frames?: number; playback_alignment?: string; native_pointer?: boolean;
  clicks?: {frame:number;x:number;y:number}[]};
type Row = {asset: string; label: string; cue: string | null; fraction: number};
type Shot = {id: string; duration: number; captions: {text: string; from: number}[]};
const assets: Record<string, Asset> = data.assets;
const scenes: Record<string, Row[]> = data.scenes;
export const hasDirectedScene = (id: string) => Boolean(scenes[id]);
const ease = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(.33, 0, .15, 1)} as const;
// Coordinates identify text/control groups in the preserved source pixels.
const flows: Record<string,string[]> = {
  'pair-result':['验证通过','建立信任','查看设备列表'],
  'pair-open':['设备列表','添加设备','交换配对信息'],
  'pair-verify':['交换配对信息','验证设备','建立信任'],
  'stage-result':['已保存为长期知识','检索阶段成果','继续后续工作'],
  'stage-open':['查看阶段记录','阅读工作进展','选择长期保留'],
  'stage-save':['选中阶段内容','点击长期保存','后续任务检索'],
  'forget-action':['核对目标','点击确认','完成遗忘'],
  'sdk-version':['桌面 0.1.12','记忆服务 0.1.12','系统向量能力'],
  'model-options':['选择模型','配置连接','保存设置'],
  'update-panel':['查看版本','检查更新','安装升级'],
  'directory-folder':['选择资料目录','开启采集','保存授权'],
  'directory-progress':['发现新资料','后台整理','保存知识'],
  'keyword-results':['输入关键词','选择结果','打开来源'],
  'brief-reading':['选择日期','查看新增记忆','回顾采集来源'],
  'forget-target':['输入指令','预览目标','核对范围'],
  'forget-confirmed':['确认目标','完成遗忘','同步状态'],
  'behavior-source-body':['应用窗口','使用时长','资料来源'],
  'manual-recalled-body':['保存记录','输入查询','核对正文'],
  'new-bill-source-detail':['电费 210.00 元','水费 68.50 元','燃气费 156.00 元'],
};
const guidance: Record<string, [number, number][]> = {
  'dreaming-review': [[.2,.51],[.63,.51],[.72,.6]],
  'directory-folder': [[.21,.25],[.56,.58],[.8,.84]],
  'shared-settings': [[.19,.3],[.59,.49],[.54,.76]],
  'manual-entry': [[.25,.22],[.42,.49],[.76,.84]],
  'edit-version-one': [[.3,.2],[.36,.49],[.64,.75]],
  'edit-version-two': [[.3,.2],[.36,.49],[.64,.75]],
  'stage-record': [[.24,.24],[.46,.46],[.72,.76]],
  'device-controls': [[.23,.24],[.57,.37],[.18,.82]],
  'agent-tools-completed': [[.23,.24],[.46,.48],[.73,.76]],
  'agent-task-recall': [[.24,.28],[.53,.5],[.74,.74]],
  'bill-recall': [[.28,.42],[.44,.56],[.68,.73]],
  'bill-citation': [[.35,.16],[.45,.24],[.6,.27]],
  'directory-approval': [[.2,.51],[.63,.51],[.78,.82]],
  'preferences': [[.32,.26],[.38,.56],[.4,.8]],
  'manual-form': [[.3,.2],[.4,.44],[.55,.64]],
  'new-bill-actions': [[.12,.18],[.43,.94],[.86,.96]],
  'new-bill-answer': [[.22,.58],[.28,.72],[.3,.79]],
  'new-bill-source': [[.42,.3],[.23,.32],[.23,.4]],
  'brief': [[.17,.16],[.24,.41],[.23,.74]],
};

const Pointer: React.FC<{x:number;y:number}> = ({x,y}) => <div style={{position:'absolute',left:x,top:y,
  width:34,height:44,pointerEvents:'none',filter:'drop-shadow(0 3px 3px #17203335)'}}>
  <svg width="34" height="44" viewBox="0 0 34 44"><path d="M3 2L3 34L11 27L18 41L24 38L17 25L29 24Z"
    fill="#fff" stroke="#172033" strokeWidth="2.2" strokeLinejoin="round"/></svg>
</div>;

const QueryControls: React.FC<{asset:Asset}> = ({asset}) => {
  const f=useCurrentFrame(), phase=Math.min(2,Math.floor(f/24));
  const targets=[[140,135],[650,702],[1034,710]];
  const [cx,cy]=targets[phase];
  const scale=1.8;
  return <div style={{position:'absolute',left:96,top:146,width:1728,height:752,overflow:'hidden',
    borderRadius:18,background:'#fff',boxShadow:'0 16px 46px #17203312',border:'1px solid #dce2ea'}}>
    <div style={{position:'absolute',left:70,top:58,fontSize:42,fontWeight:700,color:'#1456b8'}}>
      {['新建会话','填写查询问题','点击发送'][phase]}</div>
    <div style={{position:'absolute',left:70,top:220,width:1588,height:260,overflow:'hidden',borderRadius:12}}>
      <div style={{position:'absolute',left:794-cx*scale,top:130-cy*scale}}>
        <OffthreadVideo src={staticFile(asset.src)} muted style={{width:asset.width*scale,height:asset.height*scale}}/>
        {(asset.clicks??[]).map((click,i)=>{
          const age=f-click.frame;if(age<0||age>18)return null;
          const size=interpolate(age,[0,18],[10,66],ease);
          return <div key={i} style={{position:'absolute',left:click.x*scale-size/2,top:click.y*scale-size/2,
            width:size,height:size,border:'2px solid #1456b8',borderRadius:'50%',opacity:1-age/18}}/>;
        })}
      </div>
    </div>
    <div style={{position:'absolute',left:70,right:70,top:585,display:'flex',gap:26}}>
      {['新建会话','填写问题','发送查询'].map((text,i)=><div key={text} style={{flex:1,
        borderTop:`3px solid ${i===phase?'#1456b8':'#dce2ea'}`,paddingTop:24,fontSize:34,
        color:i===phase?'#1456b8':'#526477'}}><span style={{fontSize:24,marginRight:18}}>0{i+1}</span>{text}</div>)}
    </div>
  </div>;
};

const Picture: React.FC<{name:string;duration:number;label:string}> = ({name,duration,label}) => {
  const f=useCurrentFrame(), original=assets[name];
  const resultAt=original.result_from;
  if(original.result_asset&&resultAt!==undefined&&f>=resultAt)return <Sequence from={resultAt} layout="none"><Picture name={original.result_asset} duration={duration-resultAt} label="本机已建立设备信任"/></Sequence>;
  const asset=original;
  const compact=asset.height/asset.width<.29;
  const nav=name.startsWith('navigation-');
  const availableH=compact?330:690;
  const fit=Math.min(1580/asset.width,availableH/asset.height,asset.width<250?3.2:3);
  const w=asset.width*fit,h=asset.height*fit;
  const travelEnd=Math.max(50,duration-65);
  const t=interpolate(f,[24,travelEnd],[0,1],ease);
  // Keep the complete source rectangle inside the reading area throughout the move.
  // Larger details are prepared as measured crops, so currency and control labels stay whole.
  const closeZoom=compact?1:Math.min(1.065,1660/w,720/h);
  const zoom=interpolate(f,[15,75],[1,closeZoom],ease);
  const points=guidance[name]??[[.17,.3],[.55,.48],[.7,.7]];
  const p=t<.5?t*2:(t-.5)*2, a=points[t<.5?0:1],b=points[t<.5?1:2];
  const px=(a[0]+(b[0]-a[0])*p)*w,py=(a[1]+(b[1]-a[1])*p)*h;
  const focusY=a[1]+(b[1]-a[1])*p;
  const focusX=a[0]+(b[0]-a[0])*p;
  const moveX=w*zoom<=1660?(1728-w*zoom)/2:Math.max(1728-w*zoom,Math.min(0,864-focusX*w*zoom));
  const moveY=h*zoom<=720?(752-h*zoom)/2:Math.max(752-h*zoom,Math.min(0,376-focusY*h*zoom));
  const sourceFrames=asset.frames??0;
  const playFrames=Math.min(sourceFrames,duration);
  const trim=asset.playback_alignment==='start'?0:Math.max(0,sourceFrames-playFrames);
  const mediaStyle={width:w,height:h,display:'block'};
  if(name==='new-bill-actions')return <QueryControls asset={asset}/>;
  return <div style={{position:'absolute',left:96,top:146,width:1728,height:752,overflow:'hidden',
    borderRadius:18,background:'#fff',boxShadow:'0 16px 46px #17203312',border:'1px solid #dce2ea'}}>
    {compact?<div style={{position:'absolute',left:70,right:70,top:54,fontSize:42,fontWeight:700,
      color:'#1456b8'}}>{label}</div>:null}
    <div style={{position:'absolute',left:moveX,top:compact?300-h/2:moveY,
      transform:`scale(${zoom})`,transformOrigin:'0 0'}}>
      {asset.kind==='video'&&f<playFrames?
        <OffthreadVideo src={staticFile(asset.src)} trimBefore={trim} muted style={mediaStyle}/>:
        <Img src={staticFile(asset.kind==='video'?asset.end!:asset.src)} style={mediaStyle}/>}
      {asset.kind==='image'&&asset.width>=300&&!asset.native_pointer&&f>=20?<div style={{position:'absolute',left:px,top:py,transform:`scale(${1/zoom})`,transformOrigin:'0 0'}}><Pointer x={0} y={0}/></div>:null}
      {(asset.clicks??[]).map((click,i)=>{
        const age=f+trim-click.frame;
        if(age<0||age>20||f>=playFrames)return null;
        const size=interpolate(age,[0,20],[12,70],ease)/zoom;
        return <div key={i} style={{position:'absolute',left:click.x*fit-size/2,top:click.y*fit-size/2,
          width:size,height:size,border:`${2/zoom}px solid #1456b8`,borderRadius:'50%',
          opacity:interpolate(age,[0,20],[.65,0],ease),pointerEvents:'none'}}/>;
      })}
    </div>
    {compact?<div style={{position:'absolute',left:76,right:76,top:nav?480:550,display:'flex',gap:22}}>
      {(nav?['交代任务','管理记忆','连接设备','管理授权']:(flows[name]??['定位内容','核对信息','继续使用'])).map((text,i)=>{
        const active=nav?['conversation','memory','devices','settings'].findIndex(v=>name.endsWith(v)):
          Math.min(2,Math.floor(t*3));
        return <div key={text} style={{flex:1,borderTop:`3px solid ${i===active?'#1456b8':'#dce2ea'}`,
          paddingTop:24,color:i===active?'#1456b8':'#526477',fontSize:32}}>
          <span style={{fontSize:22,marginRight:14}}>0{i+1}</span>{text}</div>;
      })}
    </div>:null}
  </div>;
};

export const DirectedProductScene: React.FC<{shot:Shot}> = ({shot}) => {
  const rows=scenes[shot.id];
  const starts=rows.map(row=>{
    if(!row.cue)return 0;
    const caption=shot.captions.find(c=>c.text.startsWith(row.cue!));
    if(!caption)throw new Error(`Picture cue missing: ${shot.id}/${row.cue}`);
    return caption.from;
  });
  if(starts.some((v,i)=>i>0&&v<=starts[i-1]))throw new Error(`Picture order: ${shot.id}`);
  return <AbsoluteFill>{rows.map((row,i)=>{
    const duration=(starts[i+1]??shot.duration)-starts[i];
    return <Sequence key={row.asset+i} from={starts[i]} durationInFrames={duration}>
      <Picture name={row.asset} duration={duration} label={row.label}/>
      {assets[row.asset].height/assets[row.asset].width>=.29?<div style={{position:'absolute',left:110,
        right:110,top:915,fontSize:32,color:'#1456b8',textAlign:'center'}}>{row.label}</div>:null}
    </Sequence>;
  })}</AbsoluteFill>;
};
