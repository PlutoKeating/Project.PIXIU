import {AbsoluteFill, Audio, Composition, Sequence, staticFile, useCurrentFrame} from 'remotion';
import {BrandInkOpen} from './BrandInkOpen';
import {Fonts} from './Fonts';
import {NarratedChapter, SHARED_CHAPTER} from './NarratedChapter';

// Opening review only. Full film remains governed by storyboard/shots.json.
export const OpeningReview: React.FC = () => {
  const frame = useCurrentFrame();
  const caption = frame >= 18 && frame < 179
    ? '貔貅，面向麒麟操作系统智能体的去中心化记忆系统。'
    : frame >= 179 && frame < 295 ? '让每一台设备的记忆，彼此相通。' : '';
  return <AbsoluteFill style={{background: '#f6f7f9'}}>
    <Fonts />
    <BrandInkOpen />
    <Sequence from={15} durationInFrames={285}>
      <Audio src={staticFile('audio/voice-sample.mp3')} />
    </Sequence>
    <Sequence from={12} durationInFrames={60}>
      <Audio src={staticFile('audio/transition-soft.mp3')} volume={0.12} />
    </Sequence>
    <div style={{position: 'absolute', left: 100, right: 100, bottom: 78,
      textAlign: 'center', fontFamily: '"Noto Sans CJK SC", sans-serif',
      fontSize: 38, color: '#172033', lineHeight: 1.5}}>{caption}</div>
  </AbsoluteFill>;
};

export const Root: React.FC = () => <>
  <Composition id="PixiuOpeningReview" component={OpeningReview}
    durationInFrames={330} fps={30} width={1920} height={1080} />
  <Composition id="PixiuSharedChapterReview" component={NarratedChapter}
    durationInFrames={SHARED_CHAPTER.duration} fps={30} width={1920} height={1080} />
</>;
