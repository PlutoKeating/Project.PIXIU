import {AbsoluteFill, Img, staticFile, useCurrentFrame} from 'remotion';

const Crop: React.FC<{src: string; x: number; y: number; w: number; h: number; scale: number; width?: number; height?: number}> =
  ({src, x, y, w, h, scale, width = 3840, height = 2160}) => <div style={{position: 'relative', width: w * scale, height: h * scale, overflow: 'hidden'}}>
    <Img src={staticFile(`screens/${src}`)} style={{position: 'absolute', width: width * scale, height: height * scale, left: -x * scale, top: -y * scale}} />
  </div>;

export const BehaviorCaptureScene: React.FC = () => {
  const f = useCurrentFrame();
  return <AbsoluteFill>
    <div style={{position: 'absolute', left: 135, right: 135, top: 200}}>
      <div style={{fontSize: 38, color: '#1456b8', fontWeight: 700, marginBottom: 55}}>
        {f < 123 ? '公开窗口的使用记录，已形成行为证据' : f < 190 ? '采集由授权开关控制' : '识别与采集能力，以当前安装包为准'}
      </div>
      {f < 123 ? <>
        <Crop src="20260909-公开行为来源正文-4K.png" x={1512} y={937} w={1430} h={88} scale={1.15} />
        <div style={{fontSize: 38, marginTop: 45, marginBottom: 25}}>本次公开窗口焦点时长：118 秒</div>
        <Crop src="20260909-公开行为来源正文-4K.png" x={1570} y={1407} w={1000} h={58} scale={1.35} />
      </> : f < 190 ? <>
        <Crop src="33-capture-disabled.png" x={8} y={239} w={690} h={29} scale={2.35} width={1440} height={900} />
        <div style={{marginTop: 55}}><Crop src="33-capture-disabled.png" x={8} y={300} w={690} h={29} scale={2.35} width={1440} height={900} /></div>
        <div style={{fontSize: 38, marginTop: 55}}>关闭采集后，已有记忆仍可检索。</div>
      </> : <div style={{background: '#fff', padding: '40px 38px', fontSize: 40, lineHeight: 1.8}}>
        <div style={{color: f < 296 ? '#1456b8' : '#172033'}}>图片识别需要可用的识别适配。</div>
        {f >= 296 ? <div style={{marginTop: 35}}>当前安装包尚未具备完整图片识别能力。</div> : null}
        {f >= 420 ? <div style={{marginTop: 35}}>剪贴板与自动截图采集尚未实现。</div> : null}
      </div>}
    </div>
    <div style={{position: 'absolute', left: 135, top: 905, fontSize: 36, color: '#526477'}}>
      {f < 123 ? '原生来源裁片 · 公开 X11 窗口实测，不代表 Wayland 原生采集验收' : f < 190 ? '原生关闭状态裁片 · 行为样本保留在本机个人范围' : '当前能力边界说明'}
    </div>
  </AbsoluteFill>;
};
