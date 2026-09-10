import { AbsoluteFill, Img, interpolate, staticFile, useCurrentFrame, Easing } from 'remotion';
import {BRAND_COPY} from './brandCopy';
import timeline from './timeline.json';


const SERIF = '"Noto Sans CJK SC", sans-serif';
const MONO = '"Noto Sans CJK SC", sans-serif';
/** Context-level defaults (copy / sizes / palette), editable per clip in the workbench. */
export const SCENE_OUTRO_DEFAULTS = {
  wordmark: BRAND_COPY.wordmark,
  wordmarkSize: 138,
  description: BRAND_COPY.description,
  descriptionSize: 38,
  tagline: BRAND_COPY.slogan,
  taglineSize: 40,
  ink: '#172033',    // oklch(18% 0.006 82)
  amber: '#1456b8',  // oklch(52% 0.115 65)
  muted: '#526477',  // oklch(50% 0.006 82)
};
type SceneOutroProps = Partial<typeof SCENE_OUTRO_DEFAULTS> & {duration?: number};

// real overshoot on landing (the old bezier(0.25,0.9,0.3,1) never crossed 1)
const FLY_EASE = Easing.bezier(0.34, 1.4, 0.44, 1);
const CRANE_EASE = Easing.bezier(0.3, 0, 0.2, 1);

/** One member of the group photo: a page element flying in from off-screen
 * to its settled pose around the wordmark. Sizes are 1x CSS px (textures 2x). */
type FlyEl = {
  key: string;
  file: string;
  w: number;
  h: number;
  cx: number;
  cy: number;
  scale: number;
  rot: number; // settled rotation, deg
  dx: number; // fly-in start offset
  dy: number;
  radius: number;
  cue: number; // scene frame the 12f flight starts
};

// render order = cue order, so later arrivals stack on top
const ELS: FlyEl[] = [
  {key: 'nav', file: 'nav.png', w: 1440, h: 67.2, cx: 960, cy: 80, scale: 0.72, rot: 0, dx: 0, dy: -120, radius: 12, cue: 4},
  {key: 'task', file: 'task.png', w: 600, h: 600 * 300 / 780, cx: 280, cy: 340, scale: 0.76, rot: -5, dx: -500, dy: 0, radius: 12, cue: 7},
  {key: 'memory', file: 'memory.png', w: 720, h: 720 * 275 / 790, cx: 1630, cy: 350, scale: 0.7, rot: 4, dx: 500, dy: 0, radius: 12, cue: 10},
  {key: 'capture', file: 'capture.png', w: 720, h: 720 * 270 / 1024, cx: 1480, cy: 755, scale: 0.68, rot: -3, dx: 450, dy: 260, radius: 12, cue: 13},
  {key: 'preference', file: 'preference.png', w: 720, h: 180, cx: 280, cy: 750, scale: 0.62, rot: 3, dx: -400, dy: 300, radius: 12, cue: 16},
  {key: 'approval', file: 'approval.png', w: 720, h: 720 * 410 / 880, cx: 700, cy: 845, scale: 0.58, rot: 2, dx: 0, dy: 320, radius: 12, cue: 19},
  {key: 'shared', file: 'shared.png', w: 720, h: 162, cx: 800, cy: 225, scale: 0.62, rot: -1.5, dx: 0, dy: -240, radius: 12, cue: 22},
  {key: 'insight', file: 'insight.png', w: 720, h: 720 * 309 / 1024, cx: 1210, cy: 895, scale: 0.6, rot: -2, dx: 380, dy: 0, radius: 12, cue: 25},
  {key: 'devices', file: 'devices.png', w: 720, h: 720 * 181 / 1044, cx: 1550, cy: 170, scale: 0.63, rot: 2.5, dx: 360, dy: -200, radius: 12, cue: 28},
];

// 20 gold dust motes, all parameters index-derived (deterministic)
const DUST = Array.from({ length: 20 }, (_, i) => ({
  x: (i * 439 + 137) % 1920,
  y0: (i * 613 + 271) % 1080,
  rise: 0.3 + (i % 5) * 0.11, // px/frame upward
  swayAmp: 9 + (i % 4) * 5,
  swayFreq: 0.022 + (i % 3) * 0.008,
  phase: (i * 0.83) % (Math.PI * 2),
  size: 2 + (i % 3) * 0.5, // 2–3px
  opacity: 0.15 + ((i * 7) % 5) * 0.05, // 0.15–0.35
}));

/** Sign-off reworked as a "group photo": core elements from every page fly in
 * from off-screen in staggered beats and settle in an arc around the center;
 * then the letterpressed "AI Foundation Lab" wordmark appears while the assembled
 * elements recede slightly into the background — teammates in the back row.
 * Launch-event treatment: a crane-in camera on the whole photo layer, ghost
 * trails + landing glows on the fly-ins, a stage light behind the wordmark,
 * gold dust and a single opening light sweep for atmosphere. */
export const SceneOutroLive: React.FC<SceneOutroProps> = (props) => {
  const { wordmark, wordmarkSize, description, descriptionSize, tagline, taglineSize, ink, amber, muted } = { ...SCENE_OUTRO_DEFAULTS, ...props };
  const LETTERS = wordmark.split('');
  const captions = timeline.shots[0].captions;
  const descriptionAt = captions.find(cue => cue.text.startsWith('面向'))!.from;
  const sloganAt = captions.find(cue => cue.text.startsWith('让每一台'))!.from;
  const frame = useCurrentFrame();
  const duration = props.duration ?? 300;

  const blur = interpolate(frame, [0, 24], [0, 14], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.bezier(0.4, 0, 0.4, 1),
  });
  const rule = interpolate(frame, [58, 70], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.bezier(0.3, 0, 0.2, 1),
  });
  const tag = interpolate(frame, [descriptionAt, descriptionAt + 12], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const fadeOut = interpolate(frame, [duration - 12, duration], [1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  // as the wordmark takes the stage (42–50) the assembled elements step back
  const recede = interpolate(frame, [42, 50], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  // ---- camera crane on the whole group-photo layer (wordmark stays outside) ----
  // 0–40: crane down from a slight top angle onto the stage; 40–end: keep breathing in
  const craneT = interpolate(frame, [0, 40], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: CRANE_EASE,
  });
  const pushT = interpolate(frame, [40, duration], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });
  const camScale = 1.06 - 0.06 * craneT + 0.035 * pushT;
  const camTilt = 4 * (1 - craneT); // rotateX deg

  // opening light sweep: one wide, faint warm band crossing the screen, 2–14
  const sweepX = interpolate(frame, [2, 14], [-700, 2020], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.bezier(0.4, 0, 0.6, 1),
  });
  const sweepOpacity = interpolate(frame, [2, 5, 11, 14], [0, 0.12, 0.12, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  // stage light behind the wordmark: 0 → 0.5 → 0.25 across 42–58
  const stageLight = interpolate(frame, [42, 50, 58], [0, 0.5, 0.25], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  // closing vignette focuses the center from the wordmark beat on
  const vignette = interpolate(frame, [42, 54], [0, 0.1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  // rule extension lines: shoot out to ±320px (58–66), then fade over 6 frames
  const ruleExt = interpolate(frame, [58, 66], [0, 1], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.bezier(0.3, 0, 0.2, 1),
  });
  const ruleExtFade = interpolate(frame, [66, 72], [1, 0], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
  });

  // one breath of letter-spacing once the wordmark is fully set (62–66)
  const wordSpacing = interpolate(frame, [62, 66], [-0.01, 0.005], {
    extrapolateLeft: 'clamp',
    extrapolateRight: 'clamp',
    easing: Easing.bezier(0.3, 0, 0.2, 1),
  });


  return (
    <AbsoluteFill style={{ opacity: fadeOut }}>
      {/* ---- group-photo layer under a slow crane-in camera ---- */}
      <AbsoluteFill
        style={{
          transform: `perspective(1400px) rotateX(${camTilt}deg) scale(${camScale})`,
          transformOrigin: '50% 45%',
          clipPath: 'inset(0 0 140px 0)',
        }}
      >
        <Img src={staticFile("current/shared-workspace.png")} style={{position:"absolute",left:240,top:96,width:1440,height:888,filter:`blur(${blur}px) saturate(0.9)`}} />
        {/* warm scrim under the flying elements: keeps the center legible without washing them */}
        <AbsoluteFill style={{ background: 'radial-gradient(1200px 800px at 50% 48%, rgba(246,247,249,0.82), rgba(246,247,249,0.55) 60%, rgba(246,247,249,0.35))', pointerEvents: 'none' }} />

        {/* group photo: elements fly in from all sides and settle around the wordmark */}
        <AbsoluteFill style={{ pointerEvents: 'none' }}>
          {ELS.map((el) => {
            if (frame < el.cue) return null;

            const t = interpolate(frame, [el.cue, el.cue + 12], [0, 1], {
              extrapolateLeft: 'clamp',
              extrapolateRight: 'clamp',
              easing: FLY_EASE,
            });
            const opacity = interpolate(frame, [el.cue, el.cue + 3], [0, 1], {
              extrapolateLeft: 'clamp',
              extrapolateRight: 'clamp',
            });

            const x = el.dx * (1 - t);
            const y = el.dy * (1 - t);
            const rot = el.rot * (2 - t); // rot×2 in flight → rot settled
            const scale = el.scale * (1.12 - 0.12 * t);

            // shadow: big and soft while airborne, tightening to a dual layer at rest
            const air = Math.max(0, 1 - t);
            const shadow =
              air > 0.01
                ? `0 ${10 + 26 * air}px ${24 + 46 * air}px rgba(23,32,51,${0.16 + 0.1 * air}), 0 2px 6px rgba(23,32,51,.08)`
                : '0 10px 24px rgba(23,32,51,.16), 0 2px 6px rgba(23,32,51,.08)';

            const settledOpacity = opacity * (1 - 0.12 * recede);
            const saturate = 1 - 0.08 * recede;



            // ghost trail while airborne: a blurred faint copy lagging 8% along the path
            const linT = interpolate(frame, [el.cue, el.cue + 12], [0, 1], {
              extrapolateLeft: 'clamp',
              extrapolateRight: 'clamp',
            });
            const showGhost = linT > 0.05 && linT < 0.95;

            // landing glow: an amber spot blooming at the bbox center as the element sets
            const glow = interpolate(frame, [el.cue + 12, el.cue + 18], [0.35, 0], {
              extrapolateLeft: 'clamp',
              extrapolateRight: 'clamp',
            });
            const showGlow = frame >= el.cue + 12 && frame < el.cue + 18;
            const glowR = el.w * el.scale * 0.5;

            return (
              <div key={el.key}>
                {showGhost ? (
                  <div
                    style={{
                      position: 'absolute',
                      left: el.cx - el.w / 2,
                      top: el.cy - el.h / 2,
                      width: el.w,
                      height: el.h,
                      transform: `translate(${x + el.dx * 0.08}px, ${y + el.dy * 0.08}px) rotate(${rot}deg) scale(${scale})`,
                      transformOrigin: 'center center',
                      borderRadius: el.radius,
                      overflow: 'hidden',
                      opacity: 0.2 * Math.max(0, 1 - linT),
                      filter: 'blur(8px)',

                    }}
                  >
                    {(
                      <Img
                        src={staticFile(`current/outro-${el.file}`)}
                        style={{ position: 'absolute', inset: 0, width: el.w, height: el.h, display: 'block' }}
                      />
                    )}
                  </div>
                ) : null}
                <div
                  style={{
                    position: 'absolute',
                    left: el.cx - el.w / 2,
                    top: el.cy - el.h / 2,
                    width: el.w,
                    height: el.h,
                    transform: `translate(${x}px, ${y}px) rotate(${rot}deg) scale(${scale})`,
                    transformOrigin: 'center center',
                    borderRadius: el.radius,
                    overflow: 'hidden',
                    boxShadow: shadow,
                    opacity: settledOpacity,
                    filter: `saturate(${saturate})`,

                  }}
                >
                  {(
                    <Img
                      src={staticFile(`current/outro-${el.file}`)}
                      style={{ position: 'absolute', inset: 0, width: el.w, height: el.h, display: 'block' }}
                    />
                  )}
                </div>
                {showGlow ? (
                  <div
                    style={{
                      position: 'absolute',
                      left: el.cx - glowR,
                      top: el.cy - glowR,
                      width: glowR * 2,
                      height: glowR * 2,
                      borderRadius: '50%',
                      background: 'radial-gradient(circle, rgba(92,154,240,0.9), rgba(92,154,240,0) 70%)',
                      opacity: glow,
                      mixBlendMode: 'multiply',
                    }}
                  />
                ) : null}
              </div>
            );
          })}
        </AbsoluteFill>
      </AbsoluteFill>

      {/* ---- atmosphere: gold dust drifting up in front of the group photo ---- */}
      <AbsoluteFill style={{ pointerEvents: 'none' }}>
        {DUST.map((d, i) => {
          const y = (((d.y0 - frame * d.rise) % 1080) + 1080) % 1080;
          const x = d.x + Math.sin(frame * d.swayFreq + d.phase) * d.swayAmp;
          return (
            <div
              key={i}
              style={{
                position: 'absolute',
                left: x,
                top: y,
                width: d.size,
                height: d.size,
                borderRadius: '50%',
                background: '#7bade8',
                opacity: d.opacity,
              }}
            />
          );
        })}
      </AbsoluteFill>

      {/* opening light sweep: one wide, faint warm band left → right (2–14) */}
      {sweepOpacity > 0 ? (
        <AbsoluteFill style={{ pointerEvents: 'none', mixBlendMode: 'overlay' }}>
          <div
            style={{
              position: 'absolute',
              top: 0,
              bottom: 0,
              left: sweepX - 300,
              width: 600,
              background: 'linear-gradient(90deg, rgba(225,237,255,0), rgba(225,237,255,1) 50%, rgba(225,237,255,0))',
              opacity: sweepOpacity,
            }}
          />
        </AbsoluteFill>
      ) : null}

      {/* stage light behind the wordmark: warm top-light pooling where the logo lands */}
      {stageLight > 0 ? (
        <AbsoluteFill
          style={{
            pointerEvents: 'none',
            background: 'radial-gradient(700px 360px at 960px 470px, rgba(225,237,255,0.95), rgba(225,237,255,0.35) 55%, rgba(225,237,255,0) 75%)',
            opacity: stageLight,
          }}
        />
      ) : null}

      {/* closing vignette: faint warm-brown corners focus the center */}
      {vignette > 0 ? (
        <AbsoluteFill
          style={{
            pointerEvents: 'none',
            background: 'radial-gradient(1400px 900px at 50% 50%, rgba(23,32,51,0) 55%, rgba(23,32,51,0.7) 100%)',
            opacity: vignette,
          }}
        />
      ) : null}

      <AbsoluteFill style={{ justifyContent: 'center', alignItems: 'center', pointerEvents: 'none' }}>
        <div style={{ textAlign: 'center' }}>
          <div style={{ fontFamily: SERIF, fontSize: wordmarkSize, fontWeight: 600, color: ink, letterSpacing: `${wordSpacing}em`, display: 'flex', justifyContent: 'center' }}>
            {LETTERS.map((ch, i) => {
              const delay = Math.round(i * 1.2);
              const t = interpolate(frame, [delay, delay + 8], [0, 1], {
                extrapolateLeft: 'clamp',
                extrapolateRight: 'clamp',
                easing: Easing.bezier(0.2, 0.75, 0.3, 1),
              });
              return (
                <span
                  key={i}
                  style={{
                    opacity: t,
                    transform: `translateY(${(1 - t) * 28}px) scale(${1.35 - 0.35 * t})`,
                    filter: `blur(${(1 - t) * 8}px)`,
                    display: 'inline-block',
                    whiteSpace: 'pre',
                  }}
                >
                  {ch}
                </span>
              );
            })}
          </div>
          <div style={{ position: 'relative', height: 6, width: 260, margin: '34px auto 0' }}>
            <div style={{ position: 'absolute', inset: 0, borderRadius: 3, background: amber, transform: `scaleX(${rule})` }} />
            {/* launch lower-third: 1px amber lines shooting out from the rule ends, then fading */}
            {ruleExt > 0 && ruleExtFade > 0 ? (
              <>
                <div style={{ position: 'absolute', top: 2.5, height: 1, right: '100%', width: 190 * ruleExt, background: amber, opacity: ruleExtFade }} />
                <div style={{ position: 'absolute', top: 2.5, height: 1, left: '100%', width: 190 * ruleExt, background: amber, opacity: ruleExtFade }} />
              </>
            ) : null}
          </div>
          <div style={{ fontFamily: MONO, fontSize: descriptionSize, letterSpacing: '0.04em', color: muted, marginTop: 30, opacity: tag, textTransform: 'uppercase' }}>
            {description}
          </div>
          <div style={{fontFamily: MONO, fontSize: taglineSize, fontWeight: 600, color: ink, marginTop: 24, opacity: interpolate(frame, [sloganAt, sloganAt + 12], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp'})}}>
            {tagline}
          </div>
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};
