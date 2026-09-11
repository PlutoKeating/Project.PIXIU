import {useCurrentFrame} from 'remotion';
import {Reveal} from './PresentationMotion';
import baseline from './evaluation-baseline.json';
import timeline from './timeline.json';

export const EvaluationScene: React.FC = () => {
 const f=useCurrentFrame();
 const shot=timeline.shots.find(s=>s.id==='s28')!;
 const verified=shot.captions.find(c=>c.text.startsWith('当前麒麟'))?.from ?? Math.round(shot.duration*.78);
 return <>
  <div style={{position:'absolute',left:135,right:135,top:195}}>
   <div style={{fontSize:36,color:'#1456b8',marginBottom:40}}>历史评测 · Debian portable · {baseline.dataset}</div>
   <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:26}}>
    {baseline.metrics.map((m,i)=><Reveal key={m.name} at={20+i*15}
      style={{background:'#fff',border:'1px solid #dce2ea',borderRadius:18,padding:'24px 35px'}}>
      <div style={{fontSize:37,color:'#526477'}}>{m.label}</div>
      <div style={{fontSize:76,color:'#1456b8',fontWeight:700,marginTop:12}}>
       {m.unit==='ms'?`${Math.round(m.value)} ms`:`${Math.round(m.value*100)}%`}
       <span style={{fontSize:29,fontWeight:400,color:'#526477',marginLeft:30}}>
        {m.unit==='ms'?`${m.denominator} 次检索`:`${Math.round(m.numerator)} / ${m.denominator} 组`}
       </span>
      </div>
    </Reveal>)}
   </div>
   <Reveal at={verified} style={{marginTop:35,padding:'22px 30px',fontSize:35,color:'#1456b8',
      background:'#eaf2ff',borderRadius:14}}>
      0.1.12 V11：安装、签名升级、双 SDK 与三端协作通过
   </Reveal>
  </div>
  <div style={{position:'absolute',left:135,top:920,fontSize:28,color:'#526477'}}>
   {f<verified?'逐样本记录与统计结果':'版本、环境与实际结果共同复核'}
  </div>
 </>;
};
