import {AbsoluteFill, Audio, Img, OffthreadVideo, Sequence, interpolate, useCurrentFrame, staticFile, Easing} from 'remotion';
import timeline from './timeline.json';
import {Fonts} from './Fonts';
import {BrandInkOpen} from './BrandInkOpen';
import {PaperTitleCard} from './PaperTitleCard';
import {TimedCaption} from './NarratedChapter';
import {PageCam} from './PageCam';
import {SceneOutroLive} from './SceneOutro';
import {SharedAgentScene, SHARED_AGENT_SHOT} from './SharedAgentScene';
import {SpotlightHeroCard} from './SpotlightHeroCard';
import {BillScene} from './BillScene';
import {SyncTraceScene} from './SyncTraceScene';
import {EvaluationScene} from './EvaluationScene';
import {PreferenceHistoryScene} from './PreferenceHistoryScene';
import {InsightDocumentScene} from './InsightDocumentScene';
import {SearchEvidenceScene} from './SearchEvidenceScene';
import {ForgetTraceScene} from './ForgetTraceScene';

type Shot = typeof timeline.shots[number];
const INK = '#172033', BLUE = '#1456b8', MUTED = '#526477';
export const FILM_DURATION = timeline.duration;
export const OUTRO_SHOT = timeline.shots.find((shot) => shot.id === 's30')!;
export const SPOTLIGHT_SHOT = timeline.shots.find((shot) => shot.id === 's03')!;
// Measured on this Remotion 4.0.484 / AAC 48 kHz / MP4 pipeline;
// independent impact and narration probes agree within 0.01 frame.
export const OUTPUT_AUDIO_OFFSET_F = 1.28;
const peakStart = (target: number, sourcePeak: number) =>
  Math.max(0, Math.round(target - sourcePeak - OUTPUT_AUDIO_OFFSET_F));
export const SFX = [
  {shot: 's03', offset: peakStart(48, 21.45), src: 'audio/whoosh-big.mp3', volume: 0.10},
  {shot: 's03', offset: peakStart(60, 44.25), src: 'audio/sparkle.mp3', volume: 0.06},
  {shot: 's03', offset: peakStart(130, 3.45), src: 'audio/transition-snap.mp3', volume: 0.12},
  {shot: 's30', offset: Math.round(5 - OUTPUT_AUDIO_OFFSET_F), src: 'audio/riser-cine.mp3', volume: 0.20},
  {shot: 's30', offset: peakStart(50, 16.65), src: 'audio/impact-deep-whoosh.mp3', volume: 0.35},
  {shot: 's30', offset: peakStart(70, 44.25), src: 'audio/sparkle.mp3', volume: 0.18},
];
const SCREENS: Record<string, string[]> = {
  s04: ['50-service-version.png'],
  s06: ['70-task-running.png', '72-task-stop-result.png'],
  s10: ['10-memory-input.png', '11-memory-saved.png'],
  s11: ['30-privacy-enabled.png', '32-capture-log.png', '34-file-source.png'],
  s12: ['33-capture-disabled.png', '50-service-version.png'],
  s13: ['16-agent-recall-result.png', '12-memory-evidence.png'],
  s15: ['61-preference-history.png', '62-preference-changed.png'],
  s16: ['14-memory-edit.png', '15-memory-version.png', '64-edit-version-conflict.png'],
  s20: ['20260909-随身笔记本共享证据.png'],
  s24: ['25-forget-target.png', '26-forget-cancel-ready.png', '27-forget-complete.png'],
  s25: ['27-forget-complete.png'],
  s26: ['60-insight-digest.png'],
  s27: ['02-install-result.png', '54-model-check.png', '51-update-check.png'],
};

// Explanatory graphics are explicitly distinct from recorded product pixels.
const PANELS: Record<string, {note: string; cards: [string, string][]}> = {
  s03: {note: '能力示意 · 共享域连接多个独立智能体', cards: [
    ['书房工作站', '记录知识与任务经验'], ['随身笔记本', '检索来源，继续使用'], ['客厅一体机', '同步更新，协作记忆']]},
  s05: {note: '架构示意 · 宿主与记忆能力通过公共接口连接', cards: [
    ['麒麟智能体宿主', '会话、模型、工具与任务'], ['记忆业务引擎', '知识、偏好、冲突与遗忘'], ['基础设施', '本地存储、混合检索与去中心化同步']]},
  s09: {note: '来源示意 · 采集能力以实际运行环境为准', cards: [
    ['对话与工具', '保留会话和工具来源'], ['手动配置与文件', '用户选择内容和范围'], ['行为与图像文字', '按已接入的能力采集']]},
  s14: {note: '公共接口实测 · 四类内容已写入、检索，并只读核对存储类型', cards: [
    ['事实', '备用电池在书房左侧抽屉'], ['流程', '整理账单 → 核对金额 → 汇总'],
    ['案例', '投影无画面：重新选择输入源'], ['模板', '事项、负责人、完成时间']]},
  s17: {note: '公共接口实测 · 本次演示使用显式晋升', cards: [
    ['短期', '本轮任务要点'], ['中期', '会话整理摘要'], ['长期', '晋升后形成可检索知识']]},
  s19: {note: '三台 V11 虚拟机实测 · 同一物理宿主，独立身份与数据库', cards: [
    ['发现', '收到局域网设备广播'], ['配对', '三端完成双向信任'], ['核对', '读取节点与同步状态']]},
  s21: {note: '真实接口观测摘要 · 仅中断客厅设备的同步连接', cards: [
    ['连接中断', '客厅保留旧版本'], ['其他设备更新', '笔记本收到新版约定'], ['恢复连接', '客厅补齐修改，三端一致']]},
  s22: {note: '真实接口观测摘要 · 两端从同一版本分别修改', cards: [
    ['书房分支', '晚上九点关闭空调'], ['客厅分支', '晚上九点四十五关闭空调'], ['重连后', '三端最终正文一致']]},
  s23: {note: '公共接口实测 · 仅使用合成演示数据', cards: [
    ['个人范围', '本机可查；另外两端无此条目'], ['敏感内容', '共享写入被拒绝'], ['共享控制', '可暂停同步或解除本地信任']]},
  s28: {note: '评测指标与本轮验证 · 单次检索不能代替 P95 性能结论', cards: [
    ['质量指标', '偏好准确率、知识召回率'], ['稳定性指标', '延迟分布、冲突正确率'], ['本轮验证', '698 项基础设施测试通过；三端同步复验通过']]},
};

const PanelScene: React.FC<{shot: Shot}> = ({shot}) => {
  const frame = useCurrentFrame();
  const panel = PANELS[shot.id];
  return <AbsoluteFill style={{padding: '285px 150px 180px'}}>
    <div style={{display: 'flex', gap: 24, flexWrap: 'wrap', justifyContent: 'center'}}>
      {panel.cards.map(([title, detail], index) => {
        const cue = 8 + index * 9;
        const t = interpolate(frame, [cue, cue + 18], [0, 1], {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(0.3, 0, 0.25, 1.15)});
        return <div key={title} style={{background: '#fff', border: '1px solid #dce2ea', borderRadius: 20,
          padding: '42px 34px', width: panel.cards.length === 4 ? 720 : 495, minHeight: 210,
          boxSizing: 'border-box', opacity: Math.min(1, t), transform: `translateY(${50 * (1-t)}px)`, boxShadow: '0 14px 36px #1720330b'}}>
          <div style={{fontSize: 42, fontWeight: 700, color: BLUE, marginBottom: 25}}>{title}</div>
          <div style={{fontSize: 30, lineHeight: 1.65}}>{detail}</div>
        </div>;
      })}
    </div>
    <div style={{fontSize: 25, color: MUTED, textAlign: 'center', marginTop: 46}}>{panel.note}</div>
  </AbsoluteFill>;
};

const ScreenScene: React.FC<{shot: Shot}> = ({shot}) => {
  const frame = useCurrentFrame();
  const files = SCREENS[shot.id];
  const segment = Math.min(files.length-1, Math.floor(frame / (shot.duration / files.length)));
  const file = files[segment];
  const floating = file.startsWith('20260909-');
  const crop = shot.id === 's24' ? {x: 0, y: 190, w: 1440, h: 594}
    : {x: floating ? 120 : 0, y: 38, w: floating ? 1200 : 1440, h: 740};
  const pageH = 1920 * crop.h / crop.w;
  const zoom = Math.min(0.77, 750 / pageH);
  return <>
    <Sequence key={segment} from={Math.floor(segment * shot.duration / files.length)}>
      <PageCam src={'screens/' + file} pageH={pageH} crop={crop} keys={[
        {frame: 0, cx: 960, cy: pageH/2, zoom: zoom * 0.96, rotX: 4, rotY: -6},
        {frame: 36, cx: 960, cy: pageH/2, zoom, rotX: 0, rotY: 0},
      ]} />
    </Sequence>
    <div style={{position: 'absolute', right: 130, bottom: 125, fontSize: 21, color: MUTED}}>真实产品画面 · 合成演示数据</div>
  </>;
};

// Native recordings play once at their recorded speed; the final source frame
// then holds visibly. No synthetic cursor, looping, or invented interaction.
const RecordedScene: React.FC<{shot: Shot}> = ({shot}) => {
  const frame = useCurrentFrame();
  const key = shot.id === 's20' ? 'shared-query' : 'forgotten-query';
  const frames = shot.id === 's20' ? 360 : 300;
  const style = {position: 'absolute' as const, width: 1440, height: 900, left: -120, top: -38};
  return <>
    <div style={{position: 'absolute', left: 360, top: 170, width: 1200, height: 740, overflow: 'hidden'}}>
      {frame < frames ? <OffthreadVideo src={staticFile(`clips/${key}.mp4`)} muted style={style} />
        : <Img src={staticFile(`clips/${key}-end.png`)} style={style} />}
    </div>
    <div style={{position: 'absolute', right: 130, bottom: 125, fontSize: 21, color: MUTED}}>
      真实记忆工作区录屏 · {frame < frames ? '原速播放' : '结果定格'}
    </div>
  </>;
};

export const ShotScene: React.FC<{shot: Shot; includeAudio?: boolean; includeCaptions?: boolean;
  headingSize?: number; headingColor?: string}> =
  ({shot, includeAudio = true, includeCaptions = true, headingSize = 45, headingColor = INK}) => {
  const title = ['s02', 's18', 's29', 's30'].includes(shot.id);
  const frame = useCurrentFrame();
  return <AbsoluteFill style={{background: '#f6f7f9', color: INK, fontFamily: '"Noto Sans CJK SC", sans-serif'}}>
    {shot.id === 's30' ? <SceneOutroLive duration={shot.duration} />
      : shot.id === 's01' ? <BrandInkOpen /> : title ? <PaperTitleCard duration={shot.duration} fontSize={76}
      words={[{text: shot.title.split('，')[0], accent: true}, {text: shot.title.split('，').slice(1).join('，')}]}
      sub={shot.id === 's30' ? 'PIXIU · 面向麒麟智能体的分布式集体记忆' : shot.chapter} />
      : shot.id === 's03' ? <>
        <div style={{position: 'absolute', left: 240, top: 140, width: 1440, height: 810, overflow: 'hidden'}}>
          <div style={{position: 'absolute', width: 1920, height: 1080, transform: 'scale(0.75)', transformOrigin: '0 0'}}><SpotlightHeroCard /></div>
        </div>
        <div style={{position: 'absolute', right: 135, bottom: 145, color: MUTED, fontSize: 22}}>能力示意 · 每台设备独立保存本地副本</div>
      </>
      : shot.id === 's07' || shot.id === 's08' ? <BillScene evidence={shot.id === 's08'} />
      : shot.id === 's21' || shot.id === 's22' ? <SyncTraceScene concurrent={shot.id === 's22'} />
      : shot.id === 's28' ? <EvaluationScene />
      : shot.id === 's15' ? <PreferenceHistoryScene />
      : shot.id === 's13' ? <SearchEvidenceScene />
      : shot.id === 's26' ? <InsightDocumentScene />
      : shot.id === 's20' ? <SharedAgentScene />
      : shot.id === 's24' && frame >= 284 ? <ForgetTraceScene />
      : shot.id === 's25' ? <RecordedScene shot={shot} />
      : SCREENS[shot.id] ? <ScreenScene shot={shot} /> : <PanelScene shot={shot} />}
    {!title && shot.id !== 's01' ? <div style={{position: 'absolute', top: 58, left: 135, fontSize: headingSize, color: headingColor, fontWeight: 700}}>{shot.title}</div> : null}
    {includeAudio ? <><Sequence from={Math.max(0, Math.round(shot.audio_from - OUTPUT_AUDIO_OFFSET_F))}>
      <Audio src={staticFile(shot.audio)} />
    </Sequence>
    {SFX.filter((sfx) => sfx.shot === shot.id).map((sfx) => <Sequence key={sfx.src} from={sfx.offset}>
      <Audio src={staticFile(sfx.src)} volume={sfx.volume} />
    </Sequence>)}</> : null}
    {includeCaptions ? <TimedCaption captions={shot.captions} /> : null}
  </AbsoluteFill>;
};

export const OutroReview: React.FC = () => <AbsoluteFill><Fonts /><ShotScene shot={OUTRO_SHOT} /></AbsoluteFill>;
export const SharedAgentReview: React.FC = () => <AbsoluteFill><Fonts /><ShotScene shot={SHARED_AGENT_SHOT} /></AbsoluteFill>;
export const SpotlightReview: React.FC = () => <AbsoluteFill><Fonts /><ShotScene shot={SPOTLIGHT_SHOT} /></AbsoluteFill>;

export const DraftOverlay: React.FC = () => <div style={{position: 'absolute', top: 25, right: 35,
  fontFamily: '"Noto Sans CJK SC", sans-serif', fontSize: 20, color: MUTED, transform: 'translateZ(0)'}}>初剪审阅 · 尚未最终验收</div>;

export const FullFilmDraft: React.FC = () => <AbsoluteFill>
  <Fonts />
  {timeline.shots.map((shot) => <Sequence key={shot.id} from={shot.from} durationInFrames={shot.duration}>
    <ShotScene shot={shot} />
  </Sequence>)}
  <DraftOverlay />
</AbsoluteFill>;

const BILL_SHOTS = timeline.shots.filter((s) => ['s07', 's08'].includes(s.id));
export const BILL_DURATION = BILL_SHOTS.reduce((total, shot) => total + shot.duration, 0);
export const BillReview: React.FC = () => <AbsoluteFill><Fonts />
  {BILL_SHOTS.map((shot) => <Sequence key={shot.id} from={shot.from - BILL_SHOTS[0].from} durationInFrames={shot.duration}><ShotScene shot={shot} /></Sequence>)}
</AbsoluteFill>;
