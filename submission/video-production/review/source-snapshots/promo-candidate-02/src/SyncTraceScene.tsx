import {useCurrentFrame} from 'remotion';
import {Reveal, Steps, ease} from './PresentationMotion';
import {interpolate} from 'remotion';
import trace from './sync-trace.json';
import timeline from './timeline.json';

// A presentation of recorded API checkpoints, explicitly separate from product UI.
// Values and timestamps are copied from the preserved source, never simulated.
export const SyncTraceScene: React.FC<{concurrent?: boolean}> = ({concurrent = false}) => {
  const frame = useCurrentFrame();
  const stages = concurrent ? trace.concurrent : trace.offline;
  const shot = timeline.shots.find((s) => s.id === (concurrent ? 's22' : 's21'))!;
  const cue = (prefix: string) => shot.captions.find((c) => c.text.startsWith(prefix))!.from;
  const index = concurrent ? (frame < cue('恢复连接后') ? 0 : 1)
    : frame < cue('暂时断开') ? 0 : frame < cue('缺失的修改') ? 1 : 2;
  const stage = stages[index];
  const stageFrom = concurrent ? (index===0?18:cue('恢复连接后')) : [18,cue('暂时断开'),cue('缺失的修改')][index];
  return <div style={{position: 'absolute', left: 135, right: 135, top: 160}}>
    <div style={{fontSize: 38, color: '#1456b8', fontWeight: 700, marginBottom: 25}}>{stage.label}</div>
    <div style={{fontSize: 36, marginBottom: 35, color: '#526477'}}>家庭节能约定 · 同一知识条目 · 公共接口实测记录</div>
    <div style={{borderTop: '2px solid #dce2ea'}}>
      {stage.rows.map((row, i) => <Reveal at={stageFrom+i*9} key={`${index}-${row.device}`} style={{display: 'grid', gridTemplateColumns: '300px 190px 1fr',
        gap: 25, alignItems: 'center', padding: '17px 24px', borderBottom: '2px solid #dce2ea', background: '#fff'}}>
        <div><div style={{fontSize: 38, fontWeight: 700}}>{row.device}</div>
          <div style={{fontSize: 36, color: '#526477', marginTop: 8}}>记录 {row.time.slice(11,19)} UTC</div></div>
        <div style={{fontSize: 40, color: '#1456b8'}}>版本 {row.version}</div>
        <div style={{fontSize: 36, lineHeight: 1.45}}>{row.text}</div>
      </Reveal>)}
    </div>
    <div style={{fontSize: 36, color: '#526477', marginTop: 30}}>
      {concurrent ? (index === 0 ? '两台设备各自更新，保留修改分支。' : '重连后，三台设备读到相同内容。')
        : '仅中断客厅的同步连接；表内时间为检查点记录时刻。'}
    </div>
    <div style={{fontSize: 36, color: '#526477', marginTop: 16}}>三台 V11 虚拟机 · 同步过程回放</div>
    <div style={{display:'flex',gap:18,marginTop:34}}>{stage.rows.map((row,i)=><div key={row.device} style={{flex:1,position:'relative',height:5,background:'#dce2ea'}}><div style={{height:5,background:'#1456b8',width:`${interpolate(frame,[stageFrom+i*20,stageFrom+i*20+55],[0,100],ease)}%`}}/></div>)}</div>
  </div>;
};
