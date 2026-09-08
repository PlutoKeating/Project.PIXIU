import {AbsoluteFill, Audio, Sequence, staticFile, useCurrentFrame} from 'remotion';
import {Fonts} from './Fonts';
import {PaperTitleCard} from './PaperTitleCard';
import timeline from './timeline.json';

export const SHARED_CHAPTER = timeline.shots.find((shot) => shot.id === 's18')!;

export const CaptionText: React.FC<{text?: string; fontSize?: number; color?: string; bottom?: number}> =
  ({text = '', fontSize = 64, color = '#172033', bottom = 28}) =>
    <div style={{position: 'absolute', left: 100, right: 100, bottom,
      fontFamily: '"Noto Sans CJK SC", sans-serif', fontSize, lineHeight: 1.15,
      color, textAlign: 'center', transform: 'translateZ(0)'}}>{text}</div>;

export const TimedCaption: React.FC<{captions: typeof SHARED_CHAPTER.captions}> = ({captions}) => {
  const frame = useCurrentFrame();
  const cue = captions.find((caption) => frame >= caption.from && frame < caption.to);
  return <CaptionText text={cue?.text ?? ''} />;
};

export const NarratedChapter: React.FC = () => <AbsoluteFill>
  <Fonts />
  <PaperTitleCard duration={SHARED_CHAPTER.duration} fontSize={84}
    words={[{text: '让多台设备，'}, {text: '共同记忆', accent: true}]}
    sub="分布式集体记忆 · 共享知识与经验" />
  <Sequence from={SHARED_CHAPTER.audio_from}>
    <Audio src={staticFile(SHARED_CHAPTER.audio)} />
  </Sequence>
  <Sequence from={12} durationInFrames={60}>
    <Audio src={staticFile('audio/transition-soft.mp3')} volume={0.08} />
  </Sequence>
  <TimedCaption captions={SHARED_CHAPTER.captions} />
</AbsoluteFill>;
