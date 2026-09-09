import {AbsoluteFill, interpolate, useCurrentFrame} from 'remotion';
import flow from './flow-results.json';
import {cue, Reveal, Steps, ease} from './PresentationMotion';
export const MemoryFlowScene:React.FC=()=>{
 const f=useCurrentFrame(), sample=flow.cases[1], reused=f>=cue('s17','检索时');
 const move=interpolate(f,[cue('s17','需要长期'),cue('s17','再经晋升')+25],[0,1],ease);
 return <AbsoluteFill><div style={{position:'absolute',left:135,right:135,top:190}}>
 <div style={{fontSize:38,fontWeight:700,color:'#1456b8',marginBottom:45}}>{reused?'再次检索，找回摘要与来源':f>=cue('s17','需要长期')?'选择值得长期保留的内容':'本轮要点与会话摘要，分层整理'}</div>
 {!reused?<><div style={{display:'flex',gap:30}}>{['短期 · 本轮要点','中期 · 会话摘要','长期 · 持续复用'].map((label,i)=><Reveal key={label} at={[cue('s17','当前轮次'),cue('s17','压缩或'),cue('s17','需要长期')][i]} style={{width:530,height:365,boxSizing:'border-box',background:'#fff',padding:36,borderRadius:18,borderTop:'4px solid #1456b8'}}>
 <div style={{fontSize:40,color:'#1456b8',fontWeight:700}}>{label}</div><div style={{fontSize:38,lineHeight:1.8,marginTop:45}}>{i===0?'记录当前任务的信息':i===1?'保存会话整理后的摘要':f>=cue('s17','再经晋升')+25?'两条记录已进入长期知识':'保存有用的上下文'}</div></Reveal>)}</div>
 <div style={{position:'absolute',left:40+1090*move,top:445,padding:'18px 28px',fontSize:38,background:'#e8f0fc',borderRadius:12,color:'#1456b8'}}>选择 → 保存 → 复用</div></>
 :<Reveal at={cue('s17','检索时')} style={{background:'#fff',padding:'32px 35px',borderRadius:18}}><div style={{fontSize:38,color:'#1456b8',marginBottom:25}}>检索返回的会话摘要</div><div style={{fontSize:40,lineHeight:1.7,maxWidth:1400}}>{sample.summary}</div><Reveal at={cue('s17','并保留')} style={{fontSize:36,color:'#526477',marginTop:24}}>知识与来源一同返回</Reveal></Reveal>}
 </div><Steps labels={['记录上下文','保存到长期','带回新任务']} cues={[cue('s17','当前轮次'),cue('s17','需要长期'),cue('s17','检索时')]}/><div style={{position:'absolute',left:135,top:920,fontSize:36,color:'#526477'}}>记忆流转示意 · 接口实测摘要</div></AbsoluteFill>;
};
