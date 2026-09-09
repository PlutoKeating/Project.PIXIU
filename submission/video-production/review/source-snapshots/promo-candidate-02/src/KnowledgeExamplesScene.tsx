import {AbsoluteFill, Img, staticFile, useCurrentFrame} from 'remotion';
import {Reveal, Steps, ease} from './PresentationMotion';
import {interpolate} from 'remotion';
import data from './knowledge-examples.json';

const labels = ['事实', '流程', '案例', '模板'];
export const KnowledgeExamplesScene: React.FC = () => {
  const f = useCurrentFrame();
  return <AbsoluteFill>
    <div style={{position: 'absolute', left: 135, right: 135, top: 185}}>
      <div style={{fontSize: 38, color: '#1456b8', fontWeight: 700, marginBottom: 38}}>
        {f < 385 ? '四类公开示例，均已写入并检索到来源' : '打开来源，按原始步骤阅读'}
      </div>
      {f < 385 ? <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 28}}>
        {data.examples.map((item, i) => <Reveal at={[18,100,190,285][i]} key={item.evidence_id} style={{background: '#fff', padding: '26px 30px', borderTop: '4px solid #1456b8'}}>
          <div style={{fontSize: 38, color: '#1456b8', fontWeight: 700}}>{labels[i]} · {item.title}</div>
          <div style={{fontSize: 38, lineHeight: 1.7, marginTop: 25}}>“{item.quote}”</div>
        </Reveal>)}
      </div> : <>
        <div style={{fontSize: 38, marginBottom: 30}}>家庭图书归还流程 · 原生正文</div>
        <div style={{position: 'relative', width: 1620, height: 385, overflow: 'hidden', background: '#fff'}}>
          <div style={{position:'absolute',left:0,top:Math.min(3,Math.max(0,Math.floor((f-435)/45)))*86+12,height:66,width:5,background:'#1456b8',zIndex:2}} />
          <Img src={staticFile('screens/20260909-家庭图书归还流程-窄栏正文-4K.png')} style={{position: 'absolute', width: 5184, height: 2916, left: -1870 * 1.35, top: -1235 * 1.35}} />
        </div>
        <div style={{fontSize: 36, color: '#526477', marginTop: 30}}>核对书名 → 检查图书 → 分类归位 → 更新登记</div>
      </>}
    </div>
    <div style={{position: 'absolute', left: 135, top: 905, fontSize: 36, color: '#526477'}}>
      {f < 385 ? '事实、流程、案例与模板 · 来源内容摘录' : '原生来源裁片 · 公开合成资料 · 正文保持原样'}
    </div>
  {f>=564?<Steps labels={['相似任务','检索资料','作为执行参考']} cues={[564,615,662]} top={805}/>:null}</AbsoluteFill>;
};
