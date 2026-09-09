import {AbsoluteFill, Img, staticFile, useCurrentFrame, interpolate} from 'remotion';
import {Reveal, Steps, cue, ease} from './PresentationMotion';
const Crop: React.FC<{src:string;x:number;y:number;w:number;h:number;scale:number;width?:number;height?:number}>=({src,x,y,w,h,scale,width=3840,height=2160})=><div style={{position:'relative',width:w*scale,height:h*scale,overflow:'hidden'}}><Img src={staticFile(`screens/${src}`)} style={{position:'absolute',width:width*scale,height:height*scale,left:-x*scale,top:-y*scale}}/></div>;
export const BehaviorCaptureScene:React.FC=()=>{
 const f=useCurrentFrame(), details=cue('s12','这里的记录'), control=cue('s12','你可以'), off=cue('s12','随时关闭');
 return <AbsoluteFill><div style={{position:'absolute',left:135,right:135,top:200}}>
 <div style={{fontSize:38,color:'#1456b8',fontWeight:700,marginBottom:55}}>{f<control?'应用使用记录，帮助理解工作习惯':'采集授权，由你掌握'}</div>
 {f<control?<><Reveal at={18}><Crop src="20260909-公开行为来源正文-4K.png" x={1512} y={937} w={1250} h={88} scale={1.3}/></Reveal>
 <Reveal at={details} style={{display:'flex',alignItems:'center',gap:45,marginTop:20}}><div style={{fontSize:108,color:'#1456b8',fontVariantNumeric:'tabular-nums'}}>{Math.round(interpolate(f,[details,details+30],[0,118],ease))}<span style={{fontSize:38}}> 秒</span></div><div style={{fontSize:38}}>本次应用使用时长</div></Reveal>
 <Reveal at={details+45} style={{marginTop:0}}><Crop src="20260909-公开行为来源正文-4K.png" x={1570} y={1318} w={1000} h={133} scale={1.35}/></Reveal></>
 :<><Reveal at={control}><Crop src="33-capture-disabled.png" x={8} y={239} w={620} h={29} scale={2.6} width={1440} height={900}/></Reveal>
 <Reveal at={off} style={{fontSize:48,marginTop:65,color:'#1456b8'}}>行为采集：已关闭</Reveal></>}
 </div><Steps labels={['应用记录','使用时长','管理授权']} cues={[18,details,control]}/><div style={{position:'absolute',left:135,top: 896,fontSize:36,color:'#526477'}}>应用使用记录 · X11 窗口演示 · 原生授权设置</div></AbsoluteFill>;
};
