import React from 'react';
import {Easing, interpolate, useCurrentFrame} from 'remotion';
import timeline from './timeline.json';
export const ease = {extrapolateLeft: 'clamp', extrapolateRight: 'clamp', easing: Easing.bezier(.22,.7,.25,1)} as const;
export const cue = (id: string, prefix: string) => {
 const line = timeline.shots.find(s=>s.id===id)?.captions.find(c=>c.text.startsWith(prefix));
 if(!line) throw new Error(`Missing narration cue: ${id}/${prefix}`);
 return line.from;
};
// Editorial movement never alters recorded product content.
export const Reveal: React.FC<{at?:number;children:React.ReactNode;style?:React.CSSProperties}> = ({at=0,children,style})=>{
 const f=useCurrentFrame(); const t=interpolate(f,[at,at+20],[0,1],ease);
 return <div style={{...style,opacity:t,transform:`translateY(${24*(1-t)}px)`}}>{children}</div>;
};
export const Steps: React.FC<{labels:string[];cues:number[];top?:number}> = ({labels,cues,top=810})=>{
 const f=useCurrentFrame();
 return <div style={{position:'absolute',left:135,right:135,top,display:'flex',gap:18}}>{labels.map((label,i)=>{
 const t=interpolate(f,[cues[i],cues[i]+22],[0,1],ease);
 return <div key={label} style={{flex:1,borderTop:'3px solid #dce2ea',paddingTop:18,position:'relative',fontSize:36,color:f>=cues[i]?'#1456b8':'#526477'}}>
 <div style={{position:'absolute',top:-3,height:3,width:`${t*100}%`,background:'#1456b8'}}/><span style={{marginRight:14}}>0{i+1}</span>{label}</div>;
 })}</div>;
};
