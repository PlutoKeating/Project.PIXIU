import {Easing, Img, OffthreadVideo, Sequence, interpolate, staticFile, useCurrentFrame} from 'remotion';
import evidence from './privacy-boundary.json';

const BLUE = '#1456b8';
export const SharingBoundaryScene: React.FC = () => {
  const frame = useCurrentFrame();
  const privateStage = frame < 193;
  const sensitiveStage = frame >= 193 && frame < 284;
  const pauseStage = frame >= 284 && frame < 404;
  const confirmStage = frame >= 404 && frame < 450;
  const pausedFrame = frame - 284;
  const pan = interpolate(pausedFrame, [0, 35, 58, 85, 113], [736, 736, 1750, 1750, 736],
    {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(.4, 0, .6, 1)});
  const local = evidence.records.find((r) => r.label === '本机查询')!;
  const remote = evidence.records.filter((r) => r.label === '另一端按同一ID与范围读取');
  const denied = evidence.records.find((r) => r.label === '合成敏感输入共享拒绝')!;
  return <div style={{position: 'absolute', left: 135, right: 135, top: 165}}>
    <div style={{fontSize: 38, fontWeight: 700, color: BLUE, marginBottom: 30}}>
      {privateStage ? '私有范围：本机可用，未进入共享同步状态' : sensitiveStage ? '共享写入：合成敏感输入被拒绝'
        : pauseStage ? '暂停传输：勾选后保存同步设置' : confirmStage ? '解除信任：先确认影响范围' : '解除完成：只移除本机对书房的信任'}
    </div>
    {privateStage ? <>
      <div style={{fontSize: 38, marginBottom: 28}}>个人阅读演示约定 · 同一知识 ID 与私有范围</div>
      {[{device: '书房', result: `本机查询命中 · HTTP ${local.response.status}`},
        ...remote.map((r) => ({device: r.device, result: `按 ID 读取不存在 · HTTP ${r.response.status}`}))].map((r) =>
        <div key={r.device} style={{display: 'grid', gridTemplateColumns: '330px 1fr', background: '#fff', padding: '25px 30px', borderBottom: '2px solid #dce2ea', fontSize: 38}}>
          <strong>{r.device}</strong><span>{r.result}</span>
        </div>)}
      <div style={{fontSize: 36, marginTop: 30}}>本机同步诊断：该知识条目不存在于同步状态中。</div>
      <div style={{fontSize: 36, color: '#526477', marginTop: 22}}>公共接口请求与响应实测 · 公开合成数据</div>
    </> : sensitiveStage ? <>
      <div style={{background: '#fff', padding: '48px 40px', marginTop: 55}}>
        <div style={{fontSize: 42, color: BLUE, fontWeight: 700}}>拒绝写入 · HTTP {denied.response.status}</div>
        <div style={{fontSize: 38, marginTop: 30}}>共享范围不接受已识别的敏感内容。</div>
      </div>
      <div style={{fontSize: 36, marginTop: 32, lineHeight: 1.6}}>使用包含测试手机号的合成字符串验证。<br />这不是 OCR 截图识别效果验收。</div>
    </> : pauseStage ? <>
      <div style={{position: 'relative', width: 1650, height: 355, overflow: 'hidden', marginTop: 65, background: '#fff'}}>
        <Sequence from={284}>
          <OffthreadVideo src={staticFile('recordings/设备暂停与恢复-4K-02.mp4')} startFrom={60} playbackRate={2} muted
            style={{position: 'absolute', maxWidth: 'none', width: 4800, height: 2700, left: -pan * 1.25, top: -745 * 1.25}} />
        </Sequence>
      </div>
      <div style={{fontSize: 36, marginTop: 35}}>原生操作节选 · 两倍速 · 拍摄后已恢复未暂停状态</div>
    </> : confirmStage ? <div style={{position: 'relative', width: 1284, height: 600, overflow: 'hidden', margin: '35px auto 0'}}>
      <Img src={staticFile('screens/20260909-解除本地信任确认-4K.png')} style={{position: 'absolute', maxWidth: 'none', width: 5760, height: 3240, left: -1474 * 1.5, top: -752 * 1.5}} />
    </div> : <>
      <div style={{position: 'relative', width: 1625, height: 155, overflow: 'hidden', marginTop: 80}}>
        <Img src={staticFile('screens/20260909-已解除书房本地信任-4K.png')} style={{position: 'absolute', maxWidth: 'none', width: 4800, height: 2700, left: -736 * 1.25, top: -618 * 1.25}} />
      </div>
      <div style={{fontSize: 38, marginTop: 45, lineHeight: 1.7}}>节点接口核对：笔记本已移除书房；书房仍保留笔记本。<br />已有记忆不因解除信任而删除。</div>
      <div style={{fontSize: 36, color: '#526477', marginTop: 25}}>拍摄后已通过配对页恢复原有信任。</div>
    </>}
    <div style={{position: 'absolute', top: 745, left: 0, fontSize: 36, color: '#526477', transform: 'translateZ(0)'}}>
      {frame < 284 ? '同宿主 V11 虚拟机 · 接口观测摘要，非产品界面' : '真实界面与操作节选 · 状态保存不等于传输抑制性能验收'}
    </div>
  </div>;
};
