import {AbsoluteFill, Img, staticFile, useCurrentFrame} from 'remotion';
import {cue, Reveal, Steps, ease} from './PresentationMotion';
import {interpolate} from 'remotion';
import data from './knowledge-examples.json';

const labels = ['事实', '流程', '案例', '模板'];
export const KnowledgeExamplesScene: React.FC = () => {
  const f = useCurrentFrame();
  return <AbsoluteFill>
    <div style={{position: 'absolute', left: 135, right: 135, top: 185}}>
      <div style={{fontSize: 38, color: '#1456b8', fontWeight: 700, marginBottom: 38}}>
        {f < cue('s14','打开流程') ? '四类公开示例，均已写入并检索到来源' : '打开来源，按原始步骤阅读'}
      </div>
      {f < cue('s14','打开流程') ? <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 28}}>
        {data.examples.map((item, i) => <Reveal at={[cue('s14','记忆可以'),cue('s14','这里记录'),cue('s14','这里记录')+65,cue('s14','以及阅读')][i]} key={item.evidence_id} style={{background: '#fff', padding: '26px 30px', borderTop: '4px solid #1456b8'}}>
          <div style={{fontSize: 38, color: '#1456b8', fontWeight: 700}}>{labels[i]} · {item.title}</div>
          <div style={{fontSize: 38, lineHeight: 1.7, marginTop: 25}}>“{item.quote}”</div>
        </Reveal>)}
      </div> : <>
        <div style={{fontSize: 38, marginBottom: 30}}>活动资料中的图书整理步骤 · 0.1.12 实拍</div>
        <div style={{position: 'relative', width: 1620, height: 385, overflow: 'hidden', background: '#fff',display:'flex',alignItems:'center',justifyContent:'center'}}>
          <Img src={staticFile('current/knowledge-workflow-body.png')} style={{width:1430,height:211.2}} />
        </div>
        
      </>}
    </div>
    <div style={{position: 'absolute', left: 135, top: 905, fontSize: 36, color: '#526477'}}>
      {f < cue('s14','打开流程') ? '事实、流程、案例与模板 · 来源内容摘录' : '0.1.12 原生来源裁片 · 公开合成资料'}
    </div>
  {f>=cue('s14','遇到相似')?<Steps labels={['相似任务','检索资料','作为执行参考']} cues={[cue('s14','遇到相似'),cue('s14','再检索'),cue('s14','交给助手')]} top={805}/>:null}</AbsoluteFill>;
};
