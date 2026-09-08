import {AbsoluteFill, Easing, Img, interpolate, staticFile, useCurrentFrame} from 'remotion';

const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;
const BLUE = '#1456b8';
const QUERY = '详细说明';
// Exact type-and-filter demo timing: 3f per character, >=11f breath,
// 10f result settling, two ripple rings 3f apart, 16f push to 2.2.
// The real UI returns one row; no invented nonmatching grid is added.
const TYPE_START = 10, FILTER = 33, CLICK = 350, DETAIL = 366;
const Crop: React.FC<{src: string; x: number; y: number; w: number; h: number; scale: number}> =
  ({src, x, y, w, h, scale}) => <div style={{position: 'relative', width: w * scale, height: h * scale, overflow: 'hidden'}}>
    <Img src={staticFile(`screens/${src}`)} style={{position: 'absolute', width: 3840 * scale,
      height: 2160 * scale, left: -x * scale, top: -y * scale}} />
  </div>;

export const SearchEvidenceScene: React.FC = () => {
  const f = useCurrentFrame();
  const count = Math.max(0, Math.min(QUERY.length, Math.floor((f - TYPE_START) / 3) + 1));
  const reveal = interpolate(f, [FILTER, FILTER + 10], [0, 1], {...clamp, easing: Easing.bezier(0.35, 0, 0.2, 1)});
  const push = interpolate(f, [CLICK, DETAIL], [0, 1], {...clamp, easing: Easing.bezier(0.35, 0, 0.2, 1)});
  const detail = f >= DETAIL;
  return <AbsoluteFill>
    <div style={{position: 'absolute', left: 135, top: 175, color: BLUE, fontSize: 38, fontWeight: 700}}>
      {detail ? '查看来源：原始配置确实包含“详细说明”' : '输入内容关键词，也能找回不同标题的记忆'}
    </div>
    <div style={{position: 'absolute', inset: 0, clipPath: 'inset(255px 0 195px 0)'}}>
      {!detail ? <div style={{position: 'absolute', inset: 0,
        transform: `translate(${657 * push}px, ${-252 * push}px) scale(${1 + 1.2 * push})`, transformOrigin: '303px 792px'}}>
        <div style={{position: 'absolute', left: 135, top: 280}}>
          <Crop src="20260909-高清检索空白起点.png" x={760} y={776} w={1070} h={80} scale={1.5} />
          <div style={{position: 'absolute', left: 25, top: 13, width: 1520, height: 86, background: '#fff',
            display: 'flex', alignItems: 'center', fontSize: 42, color: '#172033'}}>
            {QUERY.slice(0, count)}
            {f >= TYPE_START - 2 && f < CLICK && (f < 22 || Math.floor((f - 22) / 8) % 2 === 0)
              ? <span style={{width: 3, height: 44, marginLeft: 3, background: BLUE}} /> : null}
          </div>
        </div>
        <div style={{position: 'absolute', left: 135, top: 470, width: 1119, height: 195,
          padding: 24, boxSizing: 'border-box', border: '1px solid #dce2ea', borderRadius: 16,
          background: '#fff', overflow: 'hidden', opacity: reveal, transform: `translateY(${8 * (1 - reveal)}px)`}}>
          <Crop src="20260909-非标题检索结果.png" x={784} y={955} w={690} h={80} scale={1.5} />
        </div>
        <div style={{position: 'absolute', left: 135, top: 710, opacity: reveal,
          border: '1px solid #dce2ea', borderRadius: 16, overflow: 'hidden'}}>
          <Crop src="20260909-非标题检索结果.png" x={758} y={1215} w={746} h={102} scale={1.5} />
        </div>
        <div style={{position: 'absolute', left: 1340, top: 475, fontSize: 36, lineHeight: 1.85, color: BLUE}}>
          <div style={{color: '#526477'}}>检索机制示意</div>
          关键词匹配<br />语义向量<br />实体关系<br />排名融合与过滤
        </div>
        {[0, 1].map((r) => {
          const cue = CLICK + r * 3;
          if (f < cue || f > cue + 10) return null;
          const t = interpolate(f, [cue, cue + 10], [0, 1], {...clamp, easing: Easing.out(Easing.cubic)});
          const radius = 14 + (r ? 64 : 40) * t;
          return <div key={r} style={{position: 'absolute', left: 303 - radius, top: 792 - radius,
            width: radius * 2, height: radius * 2, borderRadius: '50%', border: `3px solid ${BLUE}`, opacity: 1 - t}} />;
        })}
      </div> : <div style={{position: 'absolute', left: 135, top: 335}}>
        <div style={{fontSize: 38, color: '#526477', marginBottom: 30}}>命中记忆：回答风格演示 · 来源：手动配置</div>
        <Crop src="20260909-非标题检索证据.png" x={1525} y={1177} w={1000} h={100} scale={1.6} />
        <div style={{fontSize: 36, lineHeight: 1.8, marginTop: 55, color: '#526477'}}>
          查询词出现在原始证据中。<br />此处为一次实际命中，不代表各召回通道的独立评测。
        </div>
      </div>}
      <div style={{position: 'absolute', inset: 0, background: '#f6f7f9', pointerEvents: 'none',
        opacity: interpolate(f, [360, 366, 372], [0, 1, 0], clamp)}} />
    </div>
    <div style={{position: 'absolute', left: 135, top: 905, color: '#526477', fontSize: 36}}>
      真实截图动效重排 · 输入与点击为强调动画，非原速操作
    </div>
  </AbsoluteFill>;
};
