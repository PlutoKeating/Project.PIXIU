import {Img, staticFile, useCurrentFrame} from 'remotion';

const Crop: React.FC<{file: string; x: number; y: number; w: number; h: number; scale?: number}> =
  ({file, x, y, w, h, scale = 1.2}) => <div style={{position: 'relative', width: w * scale, height: h * scale, overflow: 'hidden'}}>
    <Img src={staticFile(`screens/${file}`)} style={{position: 'absolute', width: 3840 * scale,
      height: 2160 * scale, maxWidth: 'none', left: -x * scale, top: -y * scale}} />
  </div>;

export const DeviceTrustScene: React.FC = () => {
  const frame = useCurrentFrame();
  const paired = frame < 157;
  return <div style={{position: 'absolute', left: 135, right: 135, top: 165}}>
    <div style={{fontSize: 38, color: '#1456b8', fontWeight: 700, marginBottom: 24}}>
      {paired ? '交换令牌，分别建立本地信任' : '附近广播、本地信任与同步状态分别读取'}
    </div>
    {paired ? <>
      <div style={{background: '#fff', padding: 24, marginBottom: 25}}>
        <Crop file="20260909-配对恢复本地信任成功-4K.png" x={1334} y={398} w={1135} h={80} scale={1.3} />
      </div>
      <div style={{fontSize: 36, marginBottom: 18}}>笔记本配对页：已恢复对书房的本地信任</div>
      <div style={{background: '#fff', padding: 24}}>
        <Crop file="20260909-配对恢复本地信任成功-4K.png" x={1334} y={1486} w={1135} h={88} scale={1.3} />
      </div>
      <div style={{fontSize: 36, marginTop: 30, lineHeight: 1.6}}>双方节点接口核对：书房仍信任笔记本，笔记本重新信任书房。<br />这次恢复一侧信任；令牌输入过程未录入公开素材。</div>
    </> : <>
      {[
        {label: '同步状态 · 后端记录，非实时连通性检测', file: '20260909-设备节点就绪-4K.png', y: 618, h: 116},
        {label: '已信任节点 · 书房工作站', file: '20260909-选择本地信任设备-4K.png', y: 1054, h: 118},
        {label: '附近广播 · 发现不等于配对或送达', file: '20260909-附近设备广播就绪-4K.png', y: 1574, h: 98},
      ].map((row) => <div key={row.label} style={{marginBottom: 20}}>
        <div style={{fontSize: 36, marginBottom: 8}}>{row.label}</div>
        <Crop file={row.file} x={736} y={row.y} w={1370} h={row.h} scale={1.15} />
      </div>)}
    </>}
    <div style={{position: 'fixed', left: 135, top: 910, fontSize: 36, color: '#526477'}}>真实界面裁片 · 同宿主 V11 虚拟机 · 信任记录不证明知识已送达</div>
  </div>;
};
