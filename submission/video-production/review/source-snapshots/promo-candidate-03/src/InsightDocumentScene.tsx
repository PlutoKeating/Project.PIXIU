import {AbsoluteFill, Easing, Img, interpolate, OffthreadVideo, Sequence, staticFile, useCurrentFrame} from 'remotion';

const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;
const BLUE = '#1456b8';
const SHOT_START = 180;
const Crop: React.FC<{src: string; x: number; y: number; w: number; h: number; scale: number}> =
  ({src, x, y, w, h, scale}) => <div style={{position: 'relative', width: w * scale, height: h * scale, overflow: 'hidden'}}>
    <Img src={staticFile(`screens/${src}`)} style={{position: 'absolute', width: 3840 * scale,
      height: 2160 * scale, left: -x * scale, top: -y * scale}} />
  </div>;

// Adapt the exact document demo's paired 3.5f cues, 8f wipe and single caret.
// This product has one candidate and a daily counter, not a weekly report or rails.
const blocks = [
  {y: 0, h: 42, cue: 6}, {y: 43, h: 42, cue: 6}, {y: 86, h: 42, cue: 9.5},
];
export const InsightDocumentScene: React.FC = () => {
  const f = useCurrentFrame();
  const zoom = interpolate(f, [0, 22, 64, 78, 102], [1.25, 1.21, 0.997, 1.003, 0.995], clamp);
  const caret = blocks.reduce((last, b, i) => f >= b.cue && f <= b.cue + 10 ? i : last, -1);
  const focus = interpolate(f, [285, 315], [0, 1], {...clamp, easing: Easing.bezier(0.4, 0, 0.6, 1)});
  const scale = 1.2;
  const x = 730 + 770 * focus, y = 800 + 370 * focus;
  return <AbsoluteFill>
    <div style={{position: 'absolute', left: 135, top: 175, color: BLUE, fontSize: 38, fontWeight: 700}}>
      {f < SHOT_START ? '近期候选与每日采集简报' : '选择候选 → 按标题检索 → 查看来源'}
    </div>
    {f < SHOT_START ? <>
      <div style={{position: 'absolute', left: 135, top: 280, width: 1650, height: 525,
        overflow: 'hidden', background: '#fff', borderRadius: 16, border: '1px solid #dce2ea'}}>
        <div style={{position: 'absolute', left: 30, top: 30, transform: `scale(${zoom})`, transformOrigin: '0 0'}}>
          <Crop src="20260909-洞察与当日简报-4K.png" x={760} y={812} w={1250} h={130} scale={1.25} />
          {blocks.map((b, i) => {
            const t = interpolate(f, [b.cue, b.cue + 8], [0, 1], {...clamp, easing: Easing.bezier(0.4, 0, 0.6, 1)});
            return <div key={i} style={{position: 'absolute', left: 0, top: b.y * 1.25, width: 1562.5, height: b.h * 1.25}}>
              <div style={{position: 'absolute', right: 0, top: 0, bottom: 0, width: `${100 * (1 - t)}%`, background: '#fff'}} />
              {i === caret ? <div style={{position: 'absolute', left: 1562.5 * t, top: 0, width: 2, height: 38,
                background: BLUE, opacity: t < 1 ? 1 : interpolate(f, [b.cue + 8, b.cue + 10], [1, 0], clamp)}} /> : null}
            </div>;
          })}
        </div>
        <div style={{position: 'absolute', left: 30, top: 245, opacity: f >= 140 ? 1 : 0}}>
          <div style={{fontSize: 36, color: BLUE, marginBottom: 20}}>所选日期的采集日志汇总</div>
          <Crop src="20260909-洞察与当日简报-4K.png" x={760} y={1454} w={1000} h={88} scale={1.5} />
        </div>
      </div>
      <div style={{position: 'absolute', left: 135, top: 830, color: '#526477', fontSize: 36}}>
        {f < 140 ? '本机个人域 · 最近 24 小时 · 可继续检索的候选' : '手动写入产生候选；采集简报只统计采集日志。'}
      </div>
    </> : f < 340 ? <div style={{position: 'absolute', left: 135, top: 280, width: 1650, height: 590, overflow: 'hidden', borderRadius: 16}}>
      <Sequence from={SHOT_START} layout="none">
        <OffthreadVideo src={staticFile('recordings/洞察到来源-4K-02.mp4')} startFrom={90} playbackRate={2} muted
          style={{position: 'absolute', width: 3840 * scale, height: 2160 * scale, left: -x * scale, top: -y * scale}} />
      </Sequence>
    </div> : <div style={{position: 'absolute', left: 135, top: 330}}>
      <div style={{fontSize: 38, color: BLUE, marginBottom: 35}}>原始正文 · 家庭月末归档步骤</div>
      <Crop src="20260909-洞察来源正文-4K.png" x={1536} y={1180} w={1365} h={85} scale={1.2} />
      <div style={{fontSize: 36, lineHeight: 1.8, color: '#526477', marginTop: 70}}>
        沿着洞察找到正文与来源。<br />再次打开记忆，接着完成手头的工作。
      </div>
    </div>}
    <div style={{position: 'absolute', left: 135, top: 910, fontSize: 36, color: '#526477'}}>
      {f < SHOT_START ? '近期记忆，逐条展开' : f < 340 ? '真实操作录像 · 2 倍速 · 裁切放大跟随' : '真实来源正文放大 · 公开合成示例'}
    </div>
  </AbsoluteFill>;
};
