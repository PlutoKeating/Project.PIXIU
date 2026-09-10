import timeline from './timeline.json';
import {CurrentProductScene} from './CurrentProductScenes';

export const SHARED_AGENT_SHOT = timeline.shots.find((shot) => shot.id === 's20')!;
export const SharedAgentScene: React.FC = () => <CurrentProductScene shot={SHARED_AGENT_SHOT}/>;
