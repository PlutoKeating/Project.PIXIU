import {Img, OffthreadVideo, Sequence, staticFile, useCurrentFrame} from 'remotion';
import timeline from './timeline.json';

export const SHARED_AGENT_SHOT = timeline.shots.find((shot) => shot.id === 's20')!;
// The recorded interaction begins after the response completed. Its only action
// is expanding the actual work card; it must not imply generation latency.
const REPLAY_FROM = SHARED_AGENT_SHOT.captions.find((cue) => cue.text === '换到客厅，')!.from;
const REPLAY_FRAMES = Math.min(304, SHARED_AGENT_SHOT.captions.find(c=>c.text.startsWith('并注明'))!.from - REPLAY_FROM);
const REPLAY_TRIM = 304 - REPLAY_FRAMES;
const crop = {x: 1420, y: 900, width: 1320, height: 410};
const scale = 1.25;
const sourceStyle = {position: 'absolute' as const, width: 3840 * scale,
  height: 2160 * scale, left: -crop.x * scale, top: -crop.y * scale};

export const SharedAgentScene: React.FC = () => {
  const frame = useCurrentFrame();
  const request = frame < REPLAY_FROM;
  const replay = frame < REPLAY_FROM + REPLAY_FRAMES;
  return <>
    <div style={{position: 'absolute', left: 240, top: 170, color: '#1456b8', fontSize: 38, fontWeight: 700}}>
      {request ? '随身笔记本 · 会话自动沉淀' : '客厅一体机 · 记忆检索工具'}
    </div>
    {request ? <div style={{position: 'absolute', left: 240, top: 290, width: 1440,
      padding: '80px 70px', boxSizing: 'border-box', background: '#fff', borderRadius: 20}}>
      <Img src={staticFile('clips/shared-agent-user-request-4k.png')} style={{display: 'block', width: 1140, margin: '0 auto', height: 'auto'}} />
      <div style={{fontSize: 38, color: '#526477', marginTop: 55}}>原始会话请求局部 · 对话回合保存到家庭共享范围</div>
    </div> : <div style={{position: 'absolute', left: 135, top: 280,
      width: crop.width * scale, height: crop.height * scale, overflow: 'hidden', borderRadius: 12}}>
      {replay ? <Sequence from={REPLAY_FROM} durationInFrames={REPLAY_FRAMES}>
        <OffthreadVideo src={staticFile('clips/shared-agent-result-4k.mp4')} startFrom={REPLAY_TRIM} muted style={sourceStyle} />
      </Sequence> : <Img src={staticFile('screens/20260909-客厅工具展开-4K.png')} style={sourceStyle} />}
    </div>}
    <div style={{position: 'absolute', right: 240, bottom: 145, fontSize: 38, color: '#526477'}}>
      {request ? '真实产品画面 · 合成演示约定'
        : replay ? '完成后核对工具与结果 · 原速录屏' : '工具已完成 · 真实回答与知识来源定格'}
    </div>
  </>;
};
