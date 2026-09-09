import {cue} from './PresentationMotion';
import {AbsoluteFill, Img, staticFile, useCurrentFrame} from 'remotion';
import audit from './semantic-conflict.json';

const Crop: React.FC<{src: string; x: number; y: number; w: number; h: number; scale: number; nativeWidth?: number; nativeHeight?: number}> = ({src, x, y, w, h, scale, nativeWidth = 1440, nativeHeight = 900}) =>
  <div style={{position: 'relative', width: w * scale, height: h * scale, overflow: 'hidden'}}>
    <Img src={staticFile('screens/' + src)} style={{position: 'absolute', width: nativeWidth * scale, height: nativeHeight * scale, left: -x * scale, top: -y * scale}} />
  </div>;

export const ConflictAuditScene: React.FC = () => {
  const f = useCurrentFrame();
  return <AbsoluteFill>
    <div style={{position: 'absolute', left: 135, right: 135, top: 195}}>
      {f < cue('s16','旧版本提交') ? <>
        <div style={{fontSize: 38, color: '#1456b8', marginBottom: 35}}>家庭账单：核对金额，保存修改</div>
        {f >= cue('s16','编辑基于') && <div style={{marginBottom: 28}}><Crop src="15-memory-version.png" x={539} y={213} w={76} h={20} scale={2.6} /></div>}
        <Crop src={f < cue('s16','编辑基于') ? '14-memory-edit.png' : '15-memory-version.png'} x={446} y={304} w={450} h={132} scale={2.6} />
      </> : f < cue('s16','语义矛盾') ? <>
        <div style={{fontSize: 38, color: '#1456b8', marginBottom: 35}}>另一条公开记忆：旧版本保存被阻止</div>
        <Crop src="64-edit-version-conflict.png" x={447} y={302} w={557} h={48} scale={2.6} />
        <div style={{marginTop: 55}}><Crop src="64-edit-version-conflict.png" x={397} y={606} w={625} h={45} scale={2.6} /></div>
      </> : <>
        <div style={{fontSize: 38, color: '#1456b8', marginBottom: 35}}>同一书架的层数矛盾：记录保留，采用新内容</div>
        <div style={{fontSize: 48, marginBottom: 40}}>接口原值：{audit.old_value} 层 → {audit.new_value} 层</div>
        <Crop src="20260909-语义冲突审计-4K.png" x={755} y={949} w={1350} h={95} scale={1.25} nativeWidth={3840} nativeHeight={2160} />
        <div style={{fontSize: 36, color: '#526477', marginTop: 40}}>检索已返回更正后的来源；审计页面提供只读记录。</div>
      </>}
    </div>
    <div style={{position: 'absolute', left: 135, top: 905, fontSize: 36, color: '#526477'}}>
      {f < cue('s16','语义矛盾') ? '原生界面裁片 · 公开合成资料' : '原生审计裁片与接口原值 · 公开合成资料'}
    </div>
  </AbsoluteFill>;
};
