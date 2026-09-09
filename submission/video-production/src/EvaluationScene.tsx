import {useCurrentFrame, interpolate} from 'remotion';
import {Reveal, Steps, cue, ease} from './PresentationMotion';
export const EvaluationScene: React.FC = () => {
 const f=useCurrentFrame(), report=cue('s28','每个样本'), verified=cue('s28','开发回归');
 const labels=['偏好提取','知识召回','检索耗时','冲突处理'];
 return <><div style={{position:'absolute',left:135,right:135,top:200}}>
 <div style={{fontSize:38,color:'#1456b8',marginBottom:42}}>{f<report?'四个维度，逐项评测':f<verified?'逐样本记录，汇总形成报告':'开发回归与场景验证'}</div>
 {f<report?<div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:26}}>{labels.map((label,i)=><Reveal key={label} at={80+i*48} style={{background:'#fff',borderRadius:18,padding:'35px 38px'}}>
 <div style={{fontSize:38,color:'#526477'}}>0{i+1}</div><div style={{fontSize:54,marginTop:18}}>{label}</div>
 <div style={{height:4,background:'#1456b8',marginTop:28,width:`${interpolate(f,[95+i*48,130+i*48],[0,100],ease)}%`}}/></Reveal>)}</div>
 :f<verified?<div style={{display:'flex',gap:65}}><div style={{width:760}}>{labels.map((label,i)=><Reveal key={label} at={report+i*12} style={{background:'#fff',padding:'23px 30px',marginBottom:16,fontSize:38}}>{label} · 样本记录</Reveal>)}</div>
 <Reveal at={report+40} style={{background:'#fff',borderRadius:18,padding:40,width:610}}><div style={{fontSize:50,color:'#1456b8'}}>评测报告</div>{['输入与预期结果','逐项判分','统计与分析'].map(s=><div key={s} style={{fontSize:38,marginTop:38,borderBottom:'2px solid #dce2ea',paddingBottom:16}}>{s}</div>)}</Reveal></div>
 :<div style={{display:'flex',gap:36}}><Reveal at={verified} style={{background:'#fff',padding:42,borderRadius:18,flex:1}}><div style={{fontSize:38}}>基础设施回归通过</div><div style={{fontSize:110,color:'#1456b8',fontVariantNumeric:'tabular-nums',marginTop:28}}>{Math.round(interpolate(f,[verified,verified+28],[0,698],ease))}<span style={{fontSize:38}}> 项</span></div></Reveal>
 <div style={{flex:1}}>{['断连后补齐修改','并发更新后内容一致','重连后同步遗忘'].map((s,i)=><Reveal key={s} at={verified+12+i*16} style={{background:'#fff',padding:'28px 32px',marginBottom:18,fontSize:38}}>✓ {s}</Reveal>)}</div></div>}
 </div><Steps labels={['准备样本','记录结果','持续验证']} cues={[18,report,verified]} top={825}/><div style={{position:'absolute',left:135,top: 896,fontSize:36,color:'#526477'}}>评测流程示意 · 开发回归与三台 V11 虚拟机场景记录</div></>;
};
