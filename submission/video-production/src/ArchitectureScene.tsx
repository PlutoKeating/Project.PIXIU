import {AbsoluteFill, interpolate, useCurrentFrame} from 'remotion';
import {Reveal, Steps, cue, ease} from './PresentationMotion';
export const ArchitectureScene:React.FC=()=>{
 const f=useCurrentFrame(),tools=cue('s05','提供会话'),adapter=cue('s05','原创的记忆'),engine=cue('s05','把它连接');
 const link=interpolate(f,[adapter,adapter+32],[0,1],ease);
 return <AbsoluteFill>
 <div style={{position:'absolute',left:135,top:190,fontSize:38,color:'#1456b8'}}>开放麒麟智能体 + 貔貅记忆系统</div>
 <Reveal at={18} style={{position:'absolute',left:135,top:300,width:650,height:310,boxSizing:'border-box',padding:42,background:'#fff',borderRadius:22,border:'1px solid #dce2ea'}}>
 <div style={{fontSize:48,color:'#1456b8',fontWeight:700}}>智能体宿主与运行时</div>
 <Reveal at={tools} style={{fontSize:42,marginTop:48,lineHeight:1.8}}>管理会话 · 规划任务<br/>调用工具</Reveal></Reveal>
 <svg width="1920" height="1080" style={{position:'absolute',inset:0,pointerEvents:'none'}}><path d="M 800 460 L 1080 460" stroke="#1456b8" strokeWidth="5" strokeDasharray="280" strokeDashoffset={280*(1-link)}/><circle cx={800+280*link} cy={460} r={9} fill="#1456b8" opacity={link}/></svg>
 <Reveal at={adapter} style={{position:'absolute',left:805,top:355,width:265,textAlign:'center',fontSize:38,color:'#1456b8'}}>记忆适配层</Reveal>
 <Reveal at={engine} style={{position:'absolute',left:1100,top:300,width:685,height:390,boxSizing:'border-box',padding:42,background:'#fff',borderRadius:22,border:'2px solid #1456b8'}}>
 <div style={{fontSize:48,fontWeight:700,color:'#1456b8'}}>貔貅记忆系统</div>
 {['多源接入与知识检索','偏好、安全与遗忘','本地存储与设备同步'].map((s,i)=><Reveal key={s} at={engine+i*30} style={{fontSize:38,marginTop:32}}>{s}</Reveal>)}</Reveal>
 <Steps labels={['执行任务','连接记忆','沉淀与复用']} cues={[tools,adapter,engine]}/>
 <div style={{position:'absolute',left:135,top:896,fontSize:36,color:'#526477'}}>架构示意 · 通过公共接口连接</div>
 </AbsoluteFill>;
};
