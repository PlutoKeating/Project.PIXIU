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
  const cue = (prefix: string, fraction: number) => shot.captions.find((c) => c.text.startsWith(prefix))?.from ?? Math.round(shot.duration*fraction);
  const index = concurrent ? (frame < cue('再同步到',.62) ? 0 : 1)
    : frame < cue('同步连接暂停',.25) ? 0 : frame < cue('系统交换',.69) ? 1 : 2;
  const stage = stages[index];
  const stageFrom = concurrent ? (index===0?18:cue('再同步到',.62)) : [18,cue('同步连接暂停',.25),cue('系统交换',.69)][index];
  return <div style={{position: 'absolute', left: 135, right: 135, top: 160}}>
    <div style={{fontSize: 38, color: '#1456b8', fontWeight: 700, marginBottom: 25}}>{stage.label}</div>
    <div style={{fontSize: 36, marginBottom: 35, color: '#526477'}}>云杉资料移交 · 0.1.12 · 同一知识的实际记录</div>
    <div style={{display:'flex',gap:32,position:'relative'}}>
      {stage.rows.map((row, i) => <Reveal at={stageFrom+i*9} key={`${index}-${row.device}`} style={{
        flex:1, padding:'28px 30px', minHeight:425, border:'2px solid #dce2ea', borderRadius:20, background:'#fff'}}>
        <svg width="78" height="68" viewBox="0 0 78 68"><rect x="3" y="3" width="72" height="45" rx="6"
          fill="#eaf2ff" stroke="#1456b8" strokeWidth="3"/><path d="M39 48V61M21 63H57" stroke="#1456b8" strokeWidth="3"/></svg>
        <div style={{display:'flex',alignItems:'baseline',justifyContent:'space-between',marginTop:18}}>
          <div style={{fontSize:40,fontWeight:700}}>{row.device}</div>
          <div style={{fontSize:30,color:'#1456b8'}}>版本 {row.version}</div>
        </div>
        <div style={{height:3,background:'#eaf2ff',margin:'24px 0',overflow:'hidden'}}>
          <div style={{height:3,background:'#1456b8',width:`${interpolate(frame,[stageFrom+i*15,stageFrom+i*15+40],[0,100],ease)}%`}}/>
        </div>
        <div style={{fontSize:34,lineHeight:1.7}}>{row.text}</div>
      </Reveal>)}
    </div>
    <div style={{fontSize: 34, color: '#526477', marginTop: 26}}>
      {concurrent ? (index === 0 ? '两台设备各自更新，保留修改分支。' : '重连后，三台设备读到相同内容。')
        : '每台设备保有本地副本，恢复连接后交换更新。'}
    </div>
    <div style={{fontSize: 26, color: '#526477', marginTop: 14}}>三台独立 V11 虚拟机 · 实测恢复约30.5秒</div>
  </div>;
};
