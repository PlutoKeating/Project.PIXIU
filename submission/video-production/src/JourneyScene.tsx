import {AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame} from 'remotion';
import {ease} from './PresentationMotion';

type Shot={id:string;title:string;duration:number;captions:{text:string;from:number}[]};
const paths=['current/outro-task.png','current/outro-memory.png','current/outro-shared.png'];
export const JourneyScene:React.FC<{shot:Shot}>=({shot})=>{
  const f=useCurrentFrame();
  const labels=shot.id==='s18'?['选择共享空间','连接可信设备','换台电脑接着用']:['交代一次任务','积累有来源的知识','在可信设备间接续'];
  const details=shot.id==='s18'?['家庭安排与工作资料','每台设备保存本地记忆','查询安排，继续处理工作']:['核算、整理与查询','资料、安排与日常经验','交换更新，协作使用'];
  const phrases=shot.id==='s02'?['日常工作中','貔貅把这些','并在可信']:shot.id==='s18'?['把使用体验','共享记忆','继续使用']:['从一次任务','貔貅让知识','让日常经验'];
  const starts=phrases.map(p=>shot.captions.find(c=>c.text.startsWith(p))?.from??0);
  return <AbsoluteFill>
    <div style={{position:'absolute',left:96,right:96,top:50,fontSize:54,fontWeight:700}}>{shot.title}</div>
    <div style={{position:'absolute',left:96,right:96,top:210,display:'flex',gap:30}}>
      {labels.map((label,i)=>{
        const active=f>=starts[i]&&(i===2||f<starts[i+1]);
        const enter=interpolate(f,[8+i*10,32+i*10],[0,1],ease);
        const scan=interpolate(f,[starts[i],Math.min(shot.duration,starts[i]+130)],[0,1],ease);
        return <div key={label} style={{flex:1,height:578,padding:30,boxSizing:'border-box',background:'#fff',
          border:`2px solid ${active?'#1456b8':'#dce2ea'}`,borderRadius:20,opacity:enter,
          transform:`translateY(${24*(1-enter)}px)`,boxShadow:active?'0 18px 42px #1456b815':'none'}}>
          <div style={{fontSize:26,color:'#1456b8',marginBottom:26}}>0{i+1}</div>
          <div style={{height:228,overflow:'hidden',borderRadius:10,background:'#f6f7f9',position:'relative'}}>
            <Img src={staticFile(paths[i])} style={{position:'absolute',width:700,maxWidth:'none',
              left:-25-scan*48,top:25,transform:`scale(${1+.04*scan})`,transformOrigin:'0 0'}}/>
          </div>
          <div style={{fontSize:39,fontWeight:700,lineHeight:1.5,marginTop:32,color:active?'#1456b8':'#172033'}}>{label}</div>
          <div style={{fontSize:30,color:'#526477',lineHeight:1.65,marginTop:20}}>{details[i]}</div>
        </div>;
      })}
    </div>
    <svg width="1920" height="1080" style={{position:'absolute',inset:0,pointerEvents:'none'}}>
      {[0,1].map(i=>{const t=interpolate(f,[starts[i+1],starts[i+1]+38],[0,1],ease);return <g key={i}>
        <path d={`M ${365+i*590} 858 H ${365+(i+1)*590}`} stroke="#dce2ea" strokeWidth="3"/>
        <path d={`M ${365+i*590} 858 H ${365+i*590+590*t}`} stroke="#1456b8" strokeWidth="3"/>
        <circle cx={365+i*590+590*t} cy={858} r="7" fill="#1456b8" opacity={t}/></g>;})}
    </svg>
  </AbsoluteFill>;
};
