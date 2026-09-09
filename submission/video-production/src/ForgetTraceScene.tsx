import {useCurrentFrame} from 'remotion';
import {cue, Reveal} from './PresentationMotion';
import trace from './forget-trace.json';

// Recorded checkpoints, not an imitation of the product interface.
export const ForgetTraceScene: React.FC = () => {
  const frame = useCurrentFrame();
  const rejoined = frame >= cue('s24','离线设备');
  const final = frame >= cue('s24','也会更新');
  const rows = final ? trace.tombstones.map((_, i) => ({device: ['书房工作站', '随身笔记本', '客厅一体机'][i],
    status: '已标记遗忘', detail: '三端已同步删除标记'})) : [
    {device: '随身笔记本', status: '条目不存在', detail: `在线端检查：${trace.online.time.slice(11, 19)} UTC · HTTP 404`},
    {device: '客厅一体机', status: rejoined ? '条目不存在' : '仍保留版本三',
      detail: rejoined ? `重连后检查：${trace.rejoined.time.slice(11, 19)} UTC · HTTP 404`
        : `断连时检查：${trace.offline.time.slice(11, 19)} UTC · HTTP 200`},
  ];
  return <div style={{position: 'absolute', left: 135, right: 135, top: 170}}>
    <div style={{fontSize: 38, color: '#1456b8', fontWeight: 700, marginBottom: 26}}>
      {final ? '重连后的核对：三端删除标记一致' : rejoined ? '恢复连接，客厅收到遗忘结果' : '共享遗忘：在线端先失效，断连端暂存旧副本'}
    </div>
    <div style={{fontSize: 36, color: '#526477', marginBottom: 30}}>家庭节能约定 · 同一共享知识条目 · 公共接口实测</div>
    {rows.map((row, i) => <Reveal at={(final?cue('s24','也会更新'):rejoined?cue('s24','离线设备'):cue('s24','共享记忆'))+i*7} key={`${final}-${rejoined}-${row.device}`} style={{background: '#fff', borderBottom: '2px solid #dce2ea',
      padding: '25px 28px', display: 'grid', gridTemplateColumns: '280px 280px 1fr', gap: 24, alignItems: 'center'}}>
      <div style={{fontSize: 38, fontWeight: 700}}>{row.device}</div>
      <div style={{fontSize: 38, color: '#1456b8'}}>{row.status}</div>
      <div style={{fontSize: 36, lineHeight: 1.5}}>{row.detail}</div>
    </Reveal>)}
    <div style={{fontSize: 36, color: '#526477', marginTop: 30, lineHeight: 1.6}}>
      {final ? '三台设备已同步删除标记。' : '先预览目标与影响范围，再确认遗忘；本次只使用公开合成数据。'}
    </div>
    <div style={{fontSize: 36, color: '#526477', marginTop: 18}}>三台 V11 虚拟机 · 同步过程回放</div>
    <div style={{fontSize: 36, color: '#526477', marginTop: 18}}>删除标记同步到可信设备。</div>
  </div>;
};
