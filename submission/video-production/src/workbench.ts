import {narrationAudio} from './narrationAudio';
import music from './bgm.json';
import {createElement, Fragment} from 'react';
import timeline from './timeline.json';
import {Fonts} from './Fonts';
import {CaptionText} from './NarratedChapter';
import {FullFilmFinal, ShotScene, SFX, OUTPUT_AUDIO_OFFSET_F} from './FullFilm';

const Visual = ({shotId = 's01', text, headingSize = 45, headingColor = '#172033', duration}: {
  shotId?: string; text?: string; headingSize?: number; headingColor?: string; duration?: number;
}) => {
  const source = timeline.shots.find((shot) => shot.id === shotId)!;
  const shot = {...source, title: text ?? source.title, duration: duration ?? source.duration};
  return createElement(Fragment, null, createElement(Fonts),
    createElement(ShotScene, {shot, includeAudio: false, includeCaptions: false, headingSize, headingColor}));
};
const Caption = (props: Parameters<typeof CaptionText>[0]) =>
  createElement(Fragment, null, createElement(Fonts), createElement(CaptionText, props));

// Every timing derives from the exact tables used by FullFilmDraft. Narration
// goes on the audio track alongside SFX; visual clips contain no hidden audio.
export const WORKBENCH = {
  name: '貔貅 · 中文演示审阅稿', fps: timeline.fps, width: 1920, height: 1080,
  total: timeline.duration, background: '#f6f7f9',
  shots: timeline.shots.map((shot) => ({
    id: shot.id, label: shot.title, from: shot.from, duration: shot.duration,
    component: Visual, cardId: shot.id, cardName: shot.title, durationProp: 'duration',
    props: {shotId: shot.id, text: shot.title, headingSize: 45, headingColor: '#172033'},
    schema: ['s01', 's30'].includes(shot.id) ? [] : [
      {type: 'textarea', key: 'text', label: '标题', default: shot.title},
      ...(['s02', 's18', 's29'].includes(shot.id) ? [] : [
        {type: 'number', key: 'headingSize', label: '标题字号', default: 45, min: 24, max: 70},
        {type: 'color', key: 'headingColor', label: '标题颜色', default: '#172033'},
      ]),
    ],
  })),
  captions: timeline.shots.flatMap((shot) => shot.captions.map((cue, index) => ({
    id: `${shot.id}-caption-${index}`, label: cue.text, from: shot.from + cue.from,
    duration: cue.to - cue.from, component: Caption, cardId: 'caption', cardName: '中文字幕',
    props: {text: cue.text, fontSize: 60, color: '#ffffff', bottom: 64},
    schema: [
      {type: 'textarea', key: 'text', label: '字幕', default: ''},
      {type: 'number', key: 'fontSize', label: '字号', default: 60, min: 20, max: 70},
      {type: 'color', key: 'color', label: '颜色', default: '#ffffff'},
      {type: 'number', key: 'bottom', label: '距底部', default: 64, min: 0, max: 300},
    ],
  }))),
  overlays: [],
  sfx: [
    {from: 0, duration: timeline.duration, src: music.prepared, volume: music.volume, label: '背景音乐 · ZENI — With You'},
    ...timeline.shots.map((shot) => {
      const offset = Math.max(0, Math.round(shot.audio_from - OUTPUT_AUDIO_OFFSET_F));
      return {from: shot.from + offset, duration: shot.duration - offset,
        src: narrationAudio(shot.audio), volume: 1, label: `${shot.id} 中文解说`};
    }),
    ...SFX.map((sfx) => {
      const shot = timeline.shots.find((item) => item.id === sfx.shot)!;
      return {from: shot.from + sfx.offset, duration: sfx.duration ?? shot.duration - sfx.offset,
        src: sfx.src, volume: sfx.volume, label: sfx.label ?? (sfx.shot === 's30' ? '片尾音效' : '聚焦音效')};
    }),
  ],
  order: ['overlays', 'captions', 'transitions'],
  original: FullFilmFinal,
};
