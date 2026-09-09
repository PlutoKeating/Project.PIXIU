import React from 'react';
import {Img, Sequence, Easing, interpolate, staticFile, useCurrentFrame} from 'remotion';

import {Reveal} from './PresentationMotion';

const clamp = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'} as const;
const evidenceSrc = staticFile('clips/bill-source-4k.png');
// Gallery row-embed / row-embed, adapted from reference/RowEmbed-demo.tsx.
// Each rectangle is an actual screenshot slot, never reconstructed UI text.
const rows = [
  {x: 13, y: 4, top: 4, w: 1515, h: 87, bg: '#f6f7f9'},
  {x: 42, y: 250, top: 160, w: 1480, h: 63, bg: '#ffffff'},
];
const EvidenceRows: React.FC = () => {
  const frame = useCurrentFrame();
  const pan = interpolate(frame, [0, 68], [24, 0], clamp);
  return <div style={{position: 'absolute', left: 170, top: 340 + pan, width: 1580, height: 550,
    transform: 'scale(1.4)', transformOrigin: '0 0', clipPath: 'inset(-140px 455px 220px 0)'}}>
    {rows.map((r,i)=><div key={i} style={{position:'absolute',left:r.x,top:r.top,width:r.w,height:r.h,backgroundImage:`url(${evidenceSrc})`,backgroundSize:'1580px 550px',backgroundPosition:`-${r.x}px -${r.y}px`}}/>)}
    {rows.map((r, i) => {
      const cue = 12 + i * 9, land = cue + 12;
      const patchOpacity = interpolate(frame, [land, land + 2], [1, 0], clamp);
      const p = interpolate(frame, [cue, land], [0, 1], {...clamp, easing: Easing.bezier(0.3, 0, 0.25, 1)});
      const air = 1 - p;
      const scale = frame < land ? 1.06 - 0.065 * p
        : interpolate(frame, [land, land + 4], [0.995, 1], {...clamp, easing: Easing.out(Easing.quad)});
      const spread = interpolate(frame, [land, land + 5], [0, 1], {...clamp, easing: Easing.out(Easing.cubic)});
      return <React.Fragment key={i}>
        {patchOpacity > 0 && <div style={{position: 'absolute', left: r.x, top: r.top,
          width: r.w, height: r.h, background: r.bg, opacity: patchOpacity}} />}
        {frame >= cue && frame < land + 4 && <div style={{position: 'absolute',
          left: r.x, top: r.top, width: r.w, height: r.h, borderRadius: 8,
          backgroundImage: `url(${evidenceSrc})`, backgroundSize: '1580px 550px',
          backgroundPosition: `-${r.x}px -${r.y}px`,
          opacity: interpolate(frame, [cue, cue + 3], [0, 1], clamp),
          transform: `perspective(900px) translateY(${-120 * air}px) rotateX(${16 * air}deg) scale(${scale})`,
          boxShadow: `0 ${30 * air}px ${60 * air}px rgba(23,32,51,${0.22 * air}), 0 ${8 * air}px ${16 * air}px rgba(23,32,51,${0.12 * air})`, zIndex: 3}} />}
        {frame >= land && frame < land + 8 && <div style={{position: 'absolute', left: r.x,
          top: r.top, width: r.w, height: r.h, borderRadius: 8, overflow: 'hidden', zIndex: 4}}>
          <div style={{position: 'absolute', bottom: 0, left: r.w * (1-spread)/2,
            width: r.w * spread, height: 2, background: '#1456b8', boxShadow: '0 0 6px #1456b859',
            opacity: interpolate(frame, [land, land + 2, land + 8], [1, 1, 0], clamp)}} />
        </div>}
      </React.Fragment>;
    })}
  </div>;
};

// Separate native answer and provenance crops keep both complete at reading size.
const BillAnswer: React.FC = () => <>
  <div style={{position: 'absolute', left: 140, top: 240, width: 1500, height: 400, overflow: 'hidden'}}>
    <Img src={staticFile('clips/bill-answer-4k.png')} style={{position: 'absolute', width: 2296,
      height: 616, left: -49, top: -112}} />
  </div>
  <div style={{position: 'absolute', left: 140, top: 700, width: 942.5, height: 65, overflow: 'hidden'}}>
    <Img src={staticFile('clips/bill-answer-4k.png')} style={{position: 'absolute', width: 2132,
      height: 572, left: -45.5, top: -481}} />
  </div>
  <div style={{position: 'absolute', left: 140, top: 770, width: 858, height: 65, overflow: 'hidden'}}>
    <Img src={staticFile('clips/bill-answer-4k.png')} style={{position: 'absolute', width: 2132,
      height: 572, left: -988, top: -481}} />
  </div>
</>;

export const BillScene: React.FC<{evidence?: boolean}> = ({evidence = false}) => {
  const frame = useCurrentFrame();
  const source = evidence && frame >= 97;
  const input = !evidence && frame < 330;
  const file = input ? (frame < 254 ? 'bill-input-4k.png' : 'bill-saved-4k.png') : 'bill-answer-4k.png';
  return <>
    {source ? <Sequence from={97}><EvidenceRows /></Sequence> : !input ? <BillAnswer /> : <Img src={staticFile(`clips/${file}`)}
      style={input ? {position: 'absolute', width: 820, height: 965 * 820 / 1140, left: 550, top: 165}
        : {position: 'absolute', width: 1640, height: 440, left: 140, top: 330}} />}
    {input?<div style={{position:'absolute',left:145,top:285,width:360}}>{[['电费','210 元'],['水费','68.50 元'],['燃气费','156 元']].map(([label,value],i)=><Reveal key={label} at={[18,125,186][i]} style={{marginBottom:35}}><div style={{fontSize:36,color:'#526477'}}>{label}</div><div style={{fontSize:52,color:'#1456b8',marginTop:10}}>{value}</div></Reveal>)}</div>:null}
    <div style={{position: 'absolute', left: 140, bottom: 140, color: '#526477', fontSize: 36}}>
      {source ? '打开来源，查看原始记录'
        : input ? '真实录入画面 · 已选择家庭共享范围' : '真实新会话回答 · 显式记忆工具检索已核对'}
    </div>
  </>;
};
