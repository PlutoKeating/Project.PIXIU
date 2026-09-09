import {AbsoluteFill, Img, staticFile, useCurrentFrame} from 'remotion';

import {cue, Reveal, Steps} from './PresentationMotion';

const service=cue('s04','服务与能力'), scope=cue('s10','并选择'), saved=cue('s10','保存后'), ingested=cue('s11','新增文本'), source=cue('s11','还能在来源');
const Crop: React.FC<{src: string; x: number; y: number; w: number; h: number; scale?: number}> =
  ({src, x, y, w, h, scale = 2.6}) => <div style={{position: 'relative', width: w * scale, height: h * scale, overflow: 'hidden'}}>
    <Img src={staticFile('screens/' + src)} style={{position: 'absolute', width: 1440 * scale,
      height: 900 * scale, left: -x * scale, top: -y * scale}} />
  </div>;

export const NativeSetupScene: React.FC<{kind: 's04' | 's10' | 's11'}> = ({kind}) => {
  const f = useCurrentFrame();
  const stage = kind === 's04' ? (f<service?0:service) : kind==='s10' ? (f<scope?0:f<saved?scope:saved) : (f<ingested?0:f<source?ingested:source);
  return <AbsoluteFill>
    <Reveal at={stage} style={{position: 'absolute', left: 135, right: 135, top: 195}}>
      {kind === 's04' ? <>
        <div style={{fontSize: 38, color: '#1456b8', marginBottom: 35}}>
          {f < service ? '同一桌面窗口中的四个入口' : '服务与能力 · 本次读取结果'}
        </div>
        {f < service ? <Crop src="50-service-version.png" x={8} y={145} w={305} h={89} scale={3} />
          : <Crop src="50-service-version.png" x={22} y={359} w={555} h={195} />}
      </> : kind === 's10' ? <>
        <div style={{fontSize: 38, color: '#1456b8', marginBottom: 35}}>
          {f < scope ? '录入标题与正文' : f < saved ? '本例保存在个人范围 · 共享需明确选择' : '保存后检索，核对同一账单正文'}
        </div>
        {f < scope ? <Crop src="10-memory-input.png" x={435} y={232} w={548} h={194} />
          : f < saved ? <Crop src="10-memory-input.png" x={435} y={507} w={548} h={78} />
          : <>
            <Crop src="11-memory-saved.png" x={436} y={586} w={526} h={24} />
            <div style={{marginTop: 35}}><Crop src="12-memory-evidence.png" x={486} y={510} w={480} h={135} /></div>
          </>}
      </> : <>
        <div style={{fontSize: 38, color: '#1456b8', marginBottom: 35}}>
          {f < ingested ? '授权演示目录，开启目录采集' : f < source ? '活动日志 · 文件已入库' : '来源详情 · 路径与采集时刻'}
        </div>
        {f < ingested ? <>
          <Crop src="30-privacy-enabled.png" x={7} y={237} w={356} h={61} />
          <div style={{marginTop: 35}}><Crop src="30-privacy-enabled.png" x={7} y={361} w={430} h={76} /></div>
        </> : f < source ? <Crop src="32-capture-log.png" x={18} y={652} w={365} h={117} />
          : <Crop src="34-file-source.png" x={486} y={451} w={535} h={65} />}
      </>}
      {kind==='s10' && f>=scope && f<saved?<div style={{display:'flex',gap:28,marginTop:45}}><Reveal at={cue('s10','个人内容')} style={{flex:1,background:'#fff',padding:30,borderRadius:16}}><div style={{fontSize:42,color:'#1456b8'}}>个人范围</div><div style={{fontSize:38,marginTop:20}}>保留自己的资料</div></Reveal><Reveal at={cue('s10','需要协作')} style={{flex:1,background:'#fff',padding:30,borderRadius:16}}><div style={{fontSize:42,color:'#1456b8'}}>共享范围</div><Reveal at={cue('s10','才明确')} style={{fontSize:38,marginTop:20}}>选择要协作的内容</Reveal></Reveal></div>:null}
    </Reveal>
    {kind==='s04'?<Steps labels={['会话与任务','记忆与设备','服务与能力']} cues={[cue('s04','会话'),cue('s04','会话')+40,service]} top={815}/>:kind==='s10'?<Steps labels={['录入内容','选择范围','保存并检索']} cues={[cue('s10','在记忆页'),scope,saved]} top={815}/>:<Steps labels={['授权目录','文件入库','查看来源']} cues={[cue('s11','需要自动'),ingested,source]} top={815}/>}
    <div style={{position: 'absolute', left: 135, top: 920, fontSize: 36, color: '#526477'}}>
      {kind === 's04' ? '银河麒麟 V11 · 桌面实拍' : '原生页面裁片 · 公开合成演示资料'}
    </div>
  </AbsoluteFill>;
};
