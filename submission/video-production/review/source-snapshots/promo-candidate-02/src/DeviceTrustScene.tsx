import {Img, staticFile, useCurrentFrame} from 'remotion';

import {Reveal, Steps} from './PresentationMotion';

const Crop: React.FC<{file: string; x: number; y: number; w: number; h: number; scale?: number}> =
  ({file, x, y, w, h, scale = 1.2}) => <div style={{position: 'relative', width: w * scale, height: h * scale, overflow: 'hidden'}}>
    <Img src={staticFile(`screens/${file}`)} style={{position: 'absolute', width: 3840 * scale,
      height: 2160 * scale, maxWidth: 'none', left: -x * scale, top: -y * scale}} />
  </div>;

export const DeviceTrustScene: React.FC = () => {
  const frame = useCurrentFrame();
  const paired = frame < 146;
  return <div style={{position: 'absolute', left: 135, right: 135, top: 165}}>
    <div style={{fontSize: 38, color: '#1456b8', fontWeight: 700, marginBottom: 24}}>
      {paired ? '交换配对信息，建立信任' : '查看设备与同步状态'}
    </div>
    {paired ? <>
      <div style={{fontSize: 38, marginTop: 65, marginBottom: 30}}>笔记本与书房完成配对</div>
      <div style={{background: '#fff', padding: 24}}>
        <Crop file="20260909-配对恢复本地信任成功-4K.png" x={1334} y={1486} w={1135} h={88} scale={1.3} />
      </div>
      <div style={{fontSize: 38, marginTop: 45, lineHeight: 1.6}}>笔记本与书房已建立双向信任。</div>
      <div style={{fontSize: 36, marginTop: 22, color: '#526477'}}>配对完成，查看已信任设备。</div>
    </> : <>
      {[
        {label: '同步状态', file: '20260909-设备节点就绪-4K.png', y: 618, h: 76},
        {label: '已信任节点 · 书房工作站', file: '20260909-选择本地信任设备-4K.png', y: 1054, h: 118},
        {label: '附近设备', file: '20260909-附近设备广播就绪-4K.png', y: 1574, h: 98},
      ].map((row, i) => <Reveal at={[215,146,258][i]} key={row.label} style={{marginBottom: 14}}>
        <div style={{fontSize: 36, marginBottom: 8}}>{row.label}</div>
        <Crop file={row.file} x={736} y={row.y} w={1300} h={row.h} scale={1.25} />
      </Reveal>)}
    </>}
    <div style={{position: 'absolute', left: 0, top: 755, fontSize: 36, color: '#526477', transform: 'translateZ(0)'}}>可信设备，共享记忆 · V11 虚拟机演示</div>
  </div>;
};
