import {Img, OffthreadVideo, Sequence, staticFile, useCurrentFrame} from 'remotion';
import timeline from './timeline.json';

export const SHARED_AGENT_SHOT = timeline.shots.find((shot) => shot.id === 's20')!;
// The recorded interaction begins after the response completed. Its only action
// is expanding the actual work card; it must not imply generation latency.
const REPLAY_FROM = SHARED_AGENT_SHOT.captions.find((cue) => cue.text === '换到客厅，')!.from;
const REPLAY_FRAMES = 300;
const crop = {x: 408, y: 190, width: 895, height: 400};
const scale = 1440 / crop.width;
const sourceStyle = {position: 'absolute' as const, width: 1440 * scale,
  height: 900 * scale, left: -crop.x * scale, top: -crop.y * scale};

export const SharedAgentScene: React.FC = () => {
  const frame = useCurrentFrame();
  const request = frame < REPLAY_FROM;
  const replay = frame < REPLAY_FROM + REPLAY_FRAMES;
  return <>
    <div style={{position: 'absolute', left: 240, top: 170, color: '#1456b8', fontSize: 30, fontWeight: 700}}>
      {request ? '随身笔记本 · 会话自动沉淀' : '客厅一体机 · 记忆检索工具'}
    </div>
    {request ? <div style={{position: 'absolute', left: 240, top: 290, width: 1440,
      padding: '80px 70px', boxSizing: 'border-box', background: '#fff', borderRadius: 20}}>
      <Img src={staticFile('clips/shared-agent-user-request.png')} style={{width: 1300, height: 'auto'}} />
      <div style={{fontSize: 27, color: '#526477', marginTop: 55}}>原始会话请求局部 · 对话回合保存到家庭共享范围</div>
    </div> : <div style={{position: 'absolute', left: 240, top: 235,
      width: 1440, height: crop.height * scale, overflow: 'hidden', borderRadius: 12}}>
      {replay ? <Sequence from={REPLAY_FROM} durationInFrames={REPLAY_FRAMES}>
        <OffthreadVideo src={staticFile('clips/shared-agent-result.mp4')} muted style={sourceStyle} />
      </Sequence> : <Img src={staticFile('screens/20260909-客厅智能体记忆工具完成.png')} style={sourceStyle} />}
    </div>}
    <div style={{position: 'absolute', right: 240, bottom: 145, fontSize: 22, color: '#526477'}}>
      {request ? '真实产品画面 · 合成演示约定'
        : replay ? '完成后核对工具与结果 · 原速录屏' : '工具已完成 · 真实回答与知识来源定格'}
    </div>
  </>;
};
