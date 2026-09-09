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
          {f < 221 ? '每条证据保留来源、范围与质量' : f < 388 ? '同一次写入：清洗前后可核对' : '写入完成后，按范围检索到同一来源'}
        </div>
        {f < 221 ? <>
          <div style={{fontSize: 38, marginBottom: 35}}>真实会话证据 · 家庭共享约定</div>
          <div style={{position: 'relative', width: 1650, height: 76, overflow: 'hidden', background: '#fff'}}>
            <Img src={staticFile('screens/20260909-客厅原始会话证据-4K.png')} style={{position: 'absolute', width: 5760, height: 3240, left: -1512*1.5, top: -978*1.5}} />
          </div>
          <div style={{fontSize: 36, color: '#526477', marginTop: 45}}>原生界面裁片 · 会话来源与质量信息</div>
        </> : f < 388 ? <>
          <div style={{display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 28}}>
            {[
              {title: '公开合成输入', rows: ['核对书目', '核对书目', '归还原位'], note: '另含空备注；标题两侧有空格'},
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
          <div style={{fontSize: 36, marginTop: 38}}>手动合成输入实测 · 不作为行为自动采集结果</div>
        </>}
      </div>}
    <div style={{position: 'absolute', left: 135, top: 905, fontSize: 36, color: '#526477', transform: 'translateZ(0)'}}>
      {f < 130 ? '真实界面裁片复用 · 汇入示意，非 26 条新采集记录' : f < 221 ? '会话、配置与文件来源已实拍；行为自动采集仍待补证' : '公共接口请求与响应实测摘要 · 非产品界面'}
    </div>
  </AbsoluteFill>;
};
