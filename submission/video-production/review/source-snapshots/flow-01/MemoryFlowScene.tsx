import {AbsoluteFill, useCurrentFrame} from 'remotion';
import flow from './flow-results.json';

const BLUE = '#1456b8';
export const MemoryFlowScene: React.FC = () => {
  const f = useCurrentFrame();
  const promoted = f >= 217;
  const reused = f >= 372;
  const sample = flow.cases[1];
  return <AbsoluteFill>
    <div style={{position: 'absolute', left: 135, right: 135, top: 190}}>
      <div style={{fontSize: 38, fontWeight: 700, color: BLUE, marginBottom: 45}}>
        {reused ? '后续检索：同一知识与来源，摘要完整返回' : promoted ? '明确选择需要保留的上下文，再晋升' : '生命周期事件形成不同层级的上下文'}
      </div>
      {!reused ? <>
        <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 30}}>
          {flow.cases.map((item, i) => <div key={item.context_id} style={{background: '#fff', padding: '32px 35px', borderTop: `4px solid ${BLUE}`}}>
            <div style={{fontSize: 42, fontWeight: 700, color: BLUE}}>{i === 0 ? '短期上下文' : '中期上下文'}</div>
            <div style={{fontSize: 38, marginTop: 30}}>{i === 0 ? '本轮结束时记录' : '压缩前记录摘要'}</div>
            <div style={{fontSize: 38, lineHeight: 1.7, marginTop: 40}}>
              {promoted ? <>显式晋升 {item.promoted_count} 条<br />进入长期知识</> : <>服务端选择层级<br />创建上下文成功</>}
            </div>
          </div>)}
        </div>
        <div style={{fontSize: 38, lineHeight: 1.7, marginTop: 40}}>
          {promoted ? '两次晋升后，按内容检索均命中各自返回的知识 ID。' : '本例使用两条公开合成摘要；长期保留由显式晋升决定。'}
        </div>
      </> : <>
        <div style={{background: '#fff', padding: '32px 35px'}}>
          <div style={{fontSize: 38, color: BLUE, marginBottom: 25}}>实际返回的中期摘要</div>
          <div style={{fontSize: 40, lineHeight: 1.7}}>{sample.summary}</div>
        </div>
        <div style={{fontSize: 36, lineHeight: 1.75, marginTop: 30}}>
          字符预算 {sample.max_chars} · 本次未截断 · 知识与证据 ID 均一致<br />
          当前默认标题：{sample.title}；摘要内容保留在来源正文。
        </div>
      </>}
    </div>
    <div style={{position: 'absolute', left: 135, top: 905, fontSize: 36, color: '#526477'}}>
      公共接口合成事件实测 · 非产品界面或宿主自动钩子实拍
    </div>
  </AbsoluteFill>;
};
