import {AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame} from 'remotion';
import timeline from './timeline.json';
import {Reveal} from './PresentationMotion';
import categories from './preference-categories.json';

// Adapted from the exact Gallery list-stack-press demo. Three real history
// rows replace the demo's five cards; no extra versions are manufactured.
const shot = timeline.shots.find((s) => s.id === 's15')!;
const historyStart = shot.captions.find((c) => c.text.startsWith('提取后查看'))!.from;
const changedStart = shot.captions.find((c) => c.text.startsWith('后来改为'))!.from;
const CUES = [6, 18, 30];
const FLY = 22;
const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;
const blue = '#1456b8';

const Crop: React.FC<{file: string; x: number; y: number; w: number; h: number; scale: number}> =
  ({file, x, y, w, h, scale}) => <div style={{position: 'relative', width: w * scale,
    height: h * scale, overflow: 'hidden'}}>
    <Img src={staticFile(`screens/${file}`)} style={{position: 'absolute', width: 3840 * scale,
      height: 2160 * scale, left: -x * scale, top: -y * scale}} />
  </div>;

export const PreferenceHistoryScene: React.FC = () => {
  const frame = useCurrentFrame();
  if (frame < shot.captions.find(c=>c.text.startsWith('比如先要求'))!.from) return <AbsoluteFill>
    <div style={{position: 'absolute', left: 135, top: 175, fontSize: 38, color: blue, fontWeight: 700}}>
      操作习惯与安全偏好 · 提取结果
    </div>
    <div style={{position: 'absolute', left: 135, right: 135, top: 310, display: 'flex', gap: 30}}>
      {categories.cards.map((card, i) => <Reveal at={18+i*65} key={card.id} style={{flex: 1, padding: '38px 32px',
        background: '#fff', border: '1px solid #dce2ea', borderRadius: 18, fontSize: 38, lineHeight: 1.7}}>
        <div style={{color: blue, fontWeight: 700, fontSize: 44}}>{card.title} · 版本{card.version === 1 ? '一' : card.version}</div>
        <div style={{color: '#526477', marginTop: 20}}>输入来源：{card.origin}</div>
        <div style={{fontSize: 36, marginTop: 24}}>{card.key}</div>
        <div style={{marginTop: 18}}>{card.category === 'OP_HABIT'
          ? '偏好快捷键：是 · 有效信号：1'
          : '不外传偏好：是'}</div>
      </Reveal>)}
    </div>
    <div style={{position: 'absolute', left: 135, top: 830, fontSize: 36, color: '#526477', lineHeight: 1.6}}>
      偏好提取示例 · 保存使用习惯与安全要求
    </div>
  </AbsoluteFill>;
  const f = frame - historyStart;
  const history = f >= 0;
  const changed = frame >= changedStart;
  let count = 0;
  for (const cue of CUES) count += interpolate(f, [cue + FLY, cue + FLY + 8], [0, 1],
    {...clamp, easing: Easing.bezier(0.25, 0.8, 0.25, 1)});
  const anticipate = interpolate(f, [0, 6], [0, 1], {...clamp, easing: Easing.out(Easing.quad)});
  return <AbsoluteFill>
    <div style={{position: 'absolute', left: 135, top: 175, fontSize: 38, color: blue, fontWeight: 700}}>
      {history ? '三个历史版本，保留变化过程' : changed ? '当前版本三：详细说明' : '当前版本二：简洁回答'}
    </div>
    {!history ? <div style={{position: 'absolute', left: 135, top: 345, padding: 24,
      background: '#fff', border: '1px solid #dce2ea', borderRadius: 16}}>
      <Crop file={changed ? '20260909-高清偏好版本三.png' : '20260909-高清偏好版本二.png'}
        x={734} y={832} w={1170} h={177} scale={1.28} />
      <div style={{fontSize: 36, color: '#526477', marginTop: 36}}>
        {changed ? '偏好值 verbose：详细说明' : '偏好值 compact：简洁回答'}
      </div>
    </div> : <>
      <div style={{position: 'absolute', right: 150, top: 285, color: blue,
        opacity: 0.3 + 0.7 * anticipate, transform: `scale(${0.96 + 0.04 * anticipate})`,
        transformOrigin: 'right top'}}>
        <div style={{fontSize: 36}}>已展示历史版本</div>
        <div style={{height: 105, overflow: 'hidden', textAlign: 'right', marginTop: 15}}>
          <div style={{transform: `translateY(${-count * 105}px)`}}>
            {'0123'.split('').map((d) => <div key={d} style={{height: 105, lineHeight: '105px',
              fontSize: 88, fontVariantNumeric: 'tabular-nums'}}>{d}</div>)}
          </div>
        </div>
      </div>
      <div style={{position: 'absolute', right: 150, top: 555, width: 430, fontSize: 36,
        color: '#526477', lineHeight: 1.8}}>
        版本一、二：简洁回答<br />版本三：详细说明
      </div>
      <div style={{position: 'absolute', inset: 0, clipPath: 'inset(280px 0 200px 0)'}}>
      {CUES.map((cue, i) => {
        if (f < cue) return null;
        const t = interpolate(f, [cue, cue + FLY], [0, 1],
          {...clamp, easing: Easing.bezier(0.45, 0.05, 0.25, 1.12)});
        let press = 0;
        // Transfer the arriving card's impulse to already settled cards.
        for (let j = i + 1; j < CUES.length; j++) {
          const landing = CUES[j] + FLY;
          press = Math.max(press, interpolate(f, [landing, landing + 4, landing + 8], [0, 6, 0], clamp));
        }
        const air = Math.max(0, 1 - t);
        const highlight = interpolate(f, [cue + FLY + 3, cue + FLY + 10, cue + FLY + 15], [0, 1, 0], clamp);
        return <div key={cue} style={{position: 'absolute', left: 135, top: 320 + i * 185,
          padding: '12px 24px', background: '#fff', border: '1px solid #dce2ea', borderRadius: 12,
          transform: `translateY(${600 * (1 - t) + press}px) rotate(${(i % 2 ? -2 : 2) * (1 - t)}deg) scale(${1.06 - 0.06 * t})`,
          boxShadow: `0 ${2 + 30 * air}px ${8 + 56 * air}px #1720331a`}}>
          <Crop file="20260909-高清偏好版本三.png" x={755} y={1364 + i * 132} w={780} h={100} scale={1.3} />
          <div style={{position: 'absolute', left: 24, bottom: 13, height: 5,
            width: `${40 * highlight}%`, background: blue}} />
        </div>;
      })}
      <div style={{position: 'absolute', top: 310, height: 560, width: 420,
        left: interpolate(f, [60, 74], [-700, 2600], {...clamp, easing: Easing.bezier(0.45, 0, 0.35, 1)}),
        transform: 'rotate(14deg)', mixBlendMode: 'overlay', pointerEvents: 'none',
        opacity: interpolate(f, [59, 64, 70, 74], [0, 0.3, 0.3, 0], clamp),
        background: 'linear-gradient(90deg, transparent, #e6f1ff 45%, #e6f1ff 55%, transparent)'}} />
      </div>
    </>}
    <div style={{position: 'absolute', left: 135, top: 896, color: '#526477', fontSize: 36}}>
      偏好历史 · 每次更新都有记录
    </div>
  </AbsoluteFill>;
};
