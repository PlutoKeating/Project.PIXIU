import {AbsoluteFill, Img, staticFile, useCurrentFrame} from 'remotion';

const Crop: React.FC<{src: string; x: number; y: number; w: number; h: number}> = ({src, x, y, w, h}) =>
  <div style={{position: 'relative', width: w * 2.6, height: h * 2.6, overflow: 'hidden'}}>
    <Img src={staticFile('screens/' + src)} style={{position: 'absolute', width: 1440 * 2.6,
      height: 900 * 2.6, left: -x * 2.6, top: -y * 2.6}} />
  </div>;

export const NativeDeliveryScene: React.FC<{kind: 's24' | 's25' | 's27'}> = ({kind}) => {
  const f = useCurrentFrame();
  return <AbsoluteFill>
    <div style={{position: 'absolute', left: 135, right: 135, top: 195}}>
      {kind === 's24' ? <>
        <div style={{fontSize: 38, color: '#1456b8', marginBottom: 35}}>本机便笺示例 · 核对目标与影响</div>
        <Crop src="25-forget-target.png" x={21} y={430} w={502} h={89} />
        <div style={{marginTop: 45}}>{f < 171
          ? <Crop src="25-forget-target.png" x={626} y={750} w={188} h={38} />
          : <Crop src="27-forget-complete.png" x={7} y={794} w={400} h={25} />}</div>
      </> : kind === 's25' ? <>
        <div style={{fontSize: 38, color: '#1456b8', marginBottom: 35}}>本机便笺示例 · 后端确认结果</div>
        <Crop src="27-forget-complete.png" x={7} y={794} w={400} h={25} />
        <div style={{fontSize: 48, marginTop: 65, lineHeight: 1.7}}>知识失效与检索向量清理</div>
        <div style={{fontSize: 42, marginTop: 30, lineHeight: 1.7, maxWidth: 1450}}>
          不等于所有原始证据、关系和磁盘副本都已物理擦除。
        </div>
      </> : <>
        <div style={{fontSize: 38, color: '#1456b8', marginBottom: 35}}>
          {f < 184 ? '演示安装记录 · 0.1.9' : '设置 · 模型检测与更新检查结果'}
        </div>
        {f < 184 ? <>
          <Crop src="02-install-result.png" x={0} y={731} w={174} h={23} />
          <div style={{marginTop: 55}}><Crop src="02-install-result.png" x={0} y={795} w={174} h={24} /></div>
          <div style={{fontSize: 38, color: '#526477', marginTop: 65}}>安装版本与退出码取自原始终端记录</div>
        </> : <>
            <Crop src="54-model-check.png" x={501} y={361} w={360} h={29} />
            <div style={{marginTop: 35}}><Crop src="51-update-check.png" x={502} y={300} w={411} h={162} /></div>
          </>}
      </>}
    </div>
    <div style={{position: 'absolute', left: 135, top: 905, fontSize: 36, color: '#526477'}}>
      {kind === 's27' ? f < 184 ? '原生终端裁片 · 演示安装版本，最终候选待重建验证' : '原生检测与更新结果 · 本镜未执行版本升级' : '原生页面裁片与功能说明 · 公开合成便笺'}
    </div>
  </AbsoluteFill>;
};
