import {AbsoluteFill, Img, staticFile, useCurrentFrame} from 'remotion';
import {cue, Reveal} from './PresentationMotion';
import task from './agent-task.json';

const taskStart = cue('s06', '这里展示'), recallStart = cue('s06', '打开新会话'), sourceStart = cue('s06', '引用来源');
const Crop: React.FC<{x: number; y: number; w: number; h: number; scale: number}> = ({x, y, w, h, scale}) =>
  <div style={{position: 'relative', width: w * scale, height: h * scale, overflow: 'hidden'}}>
    <Img src={staticFile('screens/' + task.native.screenshot)} style={{position: 'absolute', width: 3840 * scale,
      height: 2160 * scale, left: -x * scale, top: -y * scale}} />
  </div>;

export const AgentTaskScene: React.FC = () => {
  const frame = useCurrentFrame();
  const gateway = frame < taskStart;
  return <AbsoluteFill>
    <Reveal at={frame<taskStart?0:frame<recallStart?taskStart:frame<sourceStart?recallStart:sourceStart} style={{position: 'absolute', left: 135, right: 135, top: 185}}>
      <div style={{fontSize: 38, color: '#1456b8', marginBottom: 38}}>
        {gateway ? '工具任务 · 计算、文件与联网搜索' : '桌面会话 · 秋季阅读采购复核单'}
      </div>
      {gateway ? <div style={{display: 'flex', gap: 65}}>
        <div style={{width: 700}}>
          <div style={{fontSize: 36, color: '#526477'}}>写入并回读的文件原文</div>
          <pre style={{fontFamily: 'inherit', fontSize: 48, lineHeight: 1.7, marginTop: 25}}>{task.gateway.file}</pre>
        </div>
        {<div style={{paddingTop: 10, width: 810}}>
          <div style={{fontSize: 36, color: '#526477', marginBottom: 40}}>搜索工具实际返回</div>
          <div style={{fontSize: 44, marginBottom: 25}}>{task.gateway.search_title}</div>
          <div style={{fontSize: 40, color: '#1456b8'}}>{task.gateway.search_url}</div>
        </div>}
      </div> : frame < recallStart ? <>
        <div style={{fontSize: 36, color: '#526477'}}>两轮任务后，显式保存成功</div>
        <pre style={{fontFamily: 'inherit', fontSize: 48, lineHeight: 1.7, marginTop: 25}}>{task.native.file}</pre>
      </> : frame < sourceStart ? <>
        <div style={{fontSize: 36, color: '#526477', marginBottom: 32}}>新会话 · 检索已保存的采购复核单</div>
        <Crop x={1430} y={908} w={357} h={163} scale={2} />
      </> : <>
        <div style={{fontSize: 36, color: '#526477', marginBottom: 32}}>新会话回答 · 引用与保存记录对应的知识来源</div>
        <Crop x={1450} y={1180} w={565} h={340} scale={1.5} />
      </>}
    </Reveal>
    <div style={{position: 'absolute', left: 135, top: 905, fontSize: 36, color: '#526477'}}>
      {gateway ? '工具日志与文件原文摘录 · 公开合成任务' : frame < recallStart
        ? '采购复核单 · 保存为记忆'
        : '原生界面裁片 · 显式记忆检索复用'}
    </div>
  </AbsoluteFill>;
};
