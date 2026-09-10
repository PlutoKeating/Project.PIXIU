import {AbsoluteFill, Composition} from 'remotion';
import timeline from './timeline.json';
import {Fonts} from './Fonts';
import {NarratedChapter, SHARED_CHAPTER} from './NarratedChapter';
import {ShotScene, FullFilmFinal, FullFilmDraft, BillReview, BILL_DURATION, FILM_DURATION, OutroReview, OUTRO_SHOT, SharedAgentReview, SpotlightReview, SPOTLIGHT_SHOT} from './FullFilm';
import {SHARED_AGENT_SHOT} from './SharedAgentScene';
import {CurrentMaterialsReview, CURRENT_REVIEW_DURATION} from './CurrentProductScenes';

export const OpeningReview: React.FC = () => <AbsoluteFill><Fonts /><ShotScene shot={timeline.shots[0]} /></AbsoluteFill>;

export const Root: React.FC = () => <>
  <Composition id="PixiuCurrentMaterialsReview" component={CurrentMaterialsReview}
    durationInFrames={CURRENT_REVIEW_DURATION} fps={30} width={1920} height={1080} />
  <Composition id="PixiuOpeningReview" component={OpeningReview}
    durationInFrames={timeline.shots[0].duration} fps={30} width={1920} height={1080} />
  <Composition id="PixiuSharedChapterReview" component={NarratedChapter}
    durationInFrames={SHARED_CHAPTER.duration} fps={30} width={1920} height={1080} />
  <Composition id="PixiuFullDraft" component={FullFilmDraft}
    durationInFrames={FILM_DURATION} fps={30} width={1920} height={1080} />
  <Composition id="PixiuFinalFull" component={FullFilmFinal}
    durationInFrames={FILM_DURATION} fps={30} width={1920} height={1080} />
  <Composition id="PixiuOutroReview" component={OutroReview}
    durationInFrames={OUTRO_SHOT.duration} fps={30} width={1920} height={1080} />
  <Composition id="PixiuSharedAgentReview" component={SharedAgentReview}
    durationInFrames={SHARED_AGENT_SHOT.duration} fps={30} width={1920} height={1080} />
  <Composition id="PixiuSpotlightReview" component={SpotlightReview}
    durationInFrames={SPOTLIGHT_SHOT.duration} fps={30} width={1920} height={1080} />
<Composition id="PixiuBillReview" component={BillReview} durationInFrames={BILL_DURATION} fps={30} width={1920} height={1080} />
</>;
