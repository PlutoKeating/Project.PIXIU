import {AbsoluteFill, Img, staticFile, useCurrentFrame} from 'remotion';

import {Reveal, Steps} from './PresentationMotion';

const Crop: React.FC<{src: string; x: number; y: number; w: number; h: number}> = ({src, x, y, w, h}) =>
  <div style={{position: 'relative', width: w * 2.6, height: h * 2.6, overflow: 'hidden'}}>
    <Img src={staticFile('screens/' + src)} style={{position: 'absolute', width: 1440 * 2.6,
      height: 900 * 2.6, left: -x * 2.6, top: -y * 2.6}} />
  </div>;

export const NativeDeliveryScene: React.FC<{kind: 's24' | 's27'}> = ({kind}) => {
  const f = useCurrentFrame();
  return <AbsoluteFill>
    <Reveal at={kind==='s24'?(f<171?0:171):(f<193?0:193)} style={{position: 'absolute', left: 135, right: 135, top: 195}}>
      {kind === 's24' ? <>
        <div style={{fontSize: 38, color: '#1456b8', marginBottom: 35}}>本机便笺示例 · 核对目标与影响</div>
        <Crop src="25-forget-target.png" x={21} y={430} w={502} h={89} />
        <div style={{marginTop: 45}}>{f < 171
          ? <div style={{display: 'flex', gap: 80}}>
            <div><div style={{fontSize: 36, marginBottom: 20}}>确认入口</div>
              <Crop src="25-forget-target.png" x={626} y={750} w={188} h={38} /></div>
            <div><div style={{fontSize: 36, marginBottom: 20}}>取消预览的结果</div>
              <Crop src="26-forget-cancel-ready.png" x={7} y={794} w={250} h={25} /></div>
          </div>
          : <Crop src="27-forget-complete.png" x={7} y={794} w={400} h={25} />}</div>
      </> : <>
        <div style={{fontSize: 38, color: '#1456b8', marginBottom: 35}}>
          {f < 193 ? '演示安装记录 · 0.1.9' : f<329?'设置 · 模型检测与更新检查结果':'升级流程示意'}
        </div>
        {f < 193 ? <>
          <Crop src="02-install-result.png" x={0} y={731} w={174} h={23} />
          <div style={{marginTop: 55}}><Crop src="02-install-result.png" x={0} y={795} w={174} h={24} /></div>
          <div style={{fontSize: 38, color: '#526477', marginTop: 65}}>安装版本与退出码取自原始终端记录</div>
        </> : f>=329 ? <div style={{display:'flex',gap:28,marginTop:80}}>{['签名校验','健康检查','失败恢复'].map((label,i)=><Reveal at={329+i*45} key={label} style={{flex:1,padding:36,background:'#fff',borderRadius:18}}><div style={{fontSize:70,color:'#1456b8'}}>0{i+1}</div><div style={{fontSize:44,marginTop:38}}>{label}</div></Reveal>)}</div> : <>
            <Crop src="54-model-check.png" x={501} y={361} w={360} h={29} />
            <div style={{marginTop: 35}}><Crop src="51-update-check.png" x={502} y={300} w={411} h={162} /></div>
          </>}
      </>}
    </Reveal>
    {kind==='s27'?<Steps labels={['统一安装','模型连接','维护与更新']} cues={[18,230,329]} top={825}/>:null}
    <div style={{position: 'absolute', left: 135, top: 920, fontSize: 36, color: '#526477'}}>
      {kind === 's27' ? f < 193 ? '安装完成 · 版本 0.1.9' : '模型连接与更新检查' : '原生页面裁片与功能说明 · 公开合成便笺'}
    </div>
  </AbsoluteFill>;
};
