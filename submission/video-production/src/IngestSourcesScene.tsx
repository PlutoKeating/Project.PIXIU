import {cue} from './PresentationMotion';
import {AbsoluteFill, Img, staticFile, useCurrentFrame} from 'remotion';
import {DeckDealMotion} from './DeckDealMotion';
import evidence from './ingest-results.json';

const BLUE = '#1456b8';
export const IngestSourcesScene: React.FC = () => {
  const f = useCurrentFrame();
  return <AbsoluteFill>
    {f < 130 ? <div style={{position: 'absolute', inset: 0, clipPath: 'inset(145px 0 185px 0)'}}><DeckDealMotion /></div>
      : <div style={{position: 'absolute', left: 135, right: 135, top: 200}}>
        <div style={{fontSize: 38, color: BLUE, fontWeight: 700, marginBottom: 55}}>
          {f < cue('s09','检查格式') ? '每条证据保留来源、范围与质量' : f < cue('s09','再形成') ? '同一次写入：清洗前后可核对' : '写入完成后，按范围检索到同一来源'}
        </div>
        {f < cue('s09','检查格式') ? <>
          <div style={{fontSize: 38, marginBottom: 35}}>真实会话证据 · 家庭共享约定</div>
          <div style={{position: 'relative', width: 1650, height: 260, overflow: 'hidden', background: '#fff',display:'flex',justifyContent:'center',alignItems:'center'}}>
            <Img src={staticFile('current/outro-shared.png')} style={{width:1280,height:288}} />
          </div>
          <div style={{fontSize: 36, color: '#526477', marginTop: 45}}>0.1.12 实拍 · 共享约定与来源</div>
        </> : f < cue('s09','再形成') ? <>
          <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 28}}>
            {[
              {title: '公开合成输入', rows: evidence.input_items, note: '另含空备注；标题两侧有空格'},
              {title: '实际清洗后证据', rows: evidence.items, note: '重复项合并，空备注移除，标题去空格'},
            ].map((column) => <div key={column.title} style={{background: '#fff', padding: '30px 32px'}}>
              <div style={{fontSize: 38, color: BLUE, marginBottom: 25}}>{column.title}</div>
              {column.rows.map((row, i) => <div key={i} style={{fontSize: 38, padding: '12px 0', borderBottom: '1px solid #dce2ea'}}>{row}</div>)}
              <div style={{fontSize: 36, lineHeight: 1.5, marginTop: 22}}>{column.note}</div>
            </div>)}
          </div>
          <div style={{fontSize: 38, marginTop: 35}}>质量评分 {evidence.quality} · 敏感级别 {evidence.sensitivity} · 写入已接受</div>
        </> : <>
          <div style={{background: '#fff', padding: '40px 35px'}}>
            <div style={{fontSize: 44, color: BLUE, marginBottom: 32}}>{evidence.title}</div>
            <div style={{fontSize: 38, lineHeight: 1.6}}>同一私有范围内查询命中。<br />返回的来源 ID 与本次写入证据一致。</div>
          </div>
          <div style={{fontSize: 36, marginTop: 38}}>写入内容与检索来源一一对应</div>
        </>}
      </div>}
    <div style={{position: 'absolute', left: 135, top: 905, fontSize: 36, color: '#526477', transform: 'translateZ(0)'}}>
      {f < 130 ? '多种来源汇入记忆 · 过程示意' : f < cue('s09','检查格式') ? '会话、配置、文件与行为来源均有实测记录' : '内容整理过程 · 实测记录'}
    </div>
  </AbsoluteFill>;
};
