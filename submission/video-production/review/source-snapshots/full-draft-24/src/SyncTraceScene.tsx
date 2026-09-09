import {useCurrentFrame} from 'remotion';
import trace from './sync-trace.json';
import timeline from './timeline.json';

// A presentation of recorded API checkpoints, explicitly separate from product UI.
// Values and timestamps are copied from the preserved source, never simulated.
export const SyncTraceScene: React.FC<{concurrent?: boolean}> = ({concurrent = false}) => {
  const frame = useCurrentFrame();
  const stages = concurrent ? trace.concurrent : trace.offline;
  const shot = timeline.shots.find((s) => s.id === (concurrent ? 's22' : 's21'))!;
  const cue = (prefix: string) => shot.captions.find((c) => c.text.startsWith(prefix))!.from;
  const index = concurrent ? (frame < cue('再按确定性') ? 0 : 1)
    : frame < cue('暂时断开') ? 0 : frame < cue('缺失的修改') ? 1 : 2;
  const stage = stages[index];
  return <div style={{position: 'absolute', left: 135, right: 135, top: 160}}>
    <div style={{fontSize: 38, color: '#1456b8', fontWeight: 700, marginBottom: 25}}>{stage.label}</div>
    <div style={{fontSize: 36, marginBottom: 35, color: '#526477'}}>家庭节能约定 · 同一知识条目 · 公共接口实测记录</div>
    <div style={{borderTop: '2px solid #dce2ea'}}>
      {stage.rows.map((row) => <div key={row.device} style={{display: 'grid', gridTemplateColumns: '300px 190px 1fr',
        gap: 25, alignItems: 'center', padding: '17px 24px', borderBottom: '2px solid #dce2ea', background: '#fff'}}>
        <div><div style={{fontSize: 38, fontWeight: 700}}>{row.device}</div>
          <div style={{fontSize: 36, color: '#526477', marginTop: 8}}>记录 {row.time.slice(11,19)} UTC</div></div>
        <div style={{fontSize: 40, color: '#1456b8'}}>版本 {row.version}</div>
        <div style={{fontSize: 36, lineHeight: 1.45}}>{row.text}</div>
      </div>)}
    </div>
    <div style={{fontSize: 36, color: '#526477', marginTop: 30}}>
      {concurrent ? (index === 0 ? '此时是两个不同正文分支，尚未收敛。' : '核对结果：三端正文相同；不代表全部证据列表完全相同。')
        : '仅中断客厅的同步连接；表内时间为检查点记录时刻。'}
    </div>
    <div style={{fontSize: 36, color: '#526477', marginTop: 16}}>同宿主三台 V11 虚拟机 · 检查点剪辑，非实时速度</div>
  </div>;
};
