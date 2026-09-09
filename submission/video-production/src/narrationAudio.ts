import settings from './narration-volume.json';

// Gain is baked into stereo PCM so browser playback is not capped at volume=1.
export const narrationAudio = (source: string) =>
  `${settings.prepared_directory}/${source.split('/').pop()!.replace(/\.mp3$/, '.wav')}`;
