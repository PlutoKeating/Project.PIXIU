import {AbsoluteFill, OffthreadVideo, Sequence, staticFile, useCurrentFrame} from 'remotion';
import {cue, Reveal, Steps, ease} from './PresentationMotion';
import {interpolate} from 'remotion';
import data from './knowledge-examples.json';

const labels = ['事实', '流程', '案例', '模板'];
export const KnowledgeExamplesScene: React.FC = () => {
  const f = useCurrentFrame();
  return <AbsoluteFill>
    <div style={{position: 'absolute', left: 135, right: 135, top: 185}}>
      <div style={{fontSize: 38, color: '#1456b8', fontWeight: 700, marginBottom: 38}}>
        {f < cue('s14','打开归还流程') ? '四类公开示例，均已写入并检索到来源' : '打开来源，按原始步骤阅读'}
      </div>
      {f < cue('s14','打开归还流程') ? <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 28}}>
        {data.examples.map((item, i) => <Reveal at={[cue('s14','工作经验'),cue('s14','系统可以'),cue('s14','系统可以')+65,cue('s14','案例和阅读')][i]} key={item.evidence_id} style={{background: '#fff', padding: '26px 30px', borderTop: '4px solid #1456b8'}}>
          <div style={{fontSize: 38, color: '#1456b8', fontWeight: 700}}>{labels[i]} · {item.title}</div>
          <div style={{fontSize: 38, lineHeight: 1.7, marginTop: 25}}>“{item.quote}”</div>
        </Reveal>)}
      </div> : <>
        <div style={{fontSize: 38, marginBottom: 30}}>家庭图书归还流程 · 四个操作步骤</div>
        <div style={{position: 'relative', width: 1620, height: 385, overflow: 'hidden', background: '#fff',display:'flex',alignItems:'center',justifyContent:'center'}}>
          <Sequence from={cue('s14','打开归还流程')} layout="none"><OffthreadVideo src={staticFile('directed/workflow-source.mp4')} muted style={{width:1580,height:1580*112/660}} /></Sequence>
        </div>
        
      </>}
    </div>
    <div style={{position: 'absolute', left: 135, top: 905, fontSize: 36, color: '#526477'}}>
      {f < cue('s14','打开归还流程') ? '事实、流程、案例与模板 · 来源内容摘录' : '0.1.12 原生来源裁片 · 公开合成资料'}
    </div>
  {f>=cue('s14','下次处理')?<Steps labels={['相似任务','检索资料','作为执行参考']} cues={[cue('s14','下次处理'),cue('s14','助手再调用'),cue('s14','助手再调用')]} top={805}/>:null}</AbsoluteFill>;
};
