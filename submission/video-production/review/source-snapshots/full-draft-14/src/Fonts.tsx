import {useEffect, useState} from 'react';
import {cancelRender, continueRender, delayRender, staticFile} from 'remotion';

export const Fonts: React.FC = () => {
  const [handle] = useState(() => delayRender('加载固定中文字体'));
  useEffect(() => {
    Promise.all([
      document.fonts.load('400 38px "Noto Sans CJK SC"'),
      document.fonts.load('700 144px "Noto Sans CJK SC"'),
    ]).then(() => continueRender(handle)).catch(cancelRender);
  }, [handle]);
  return <style>{`
    @font-face {font-family:"Noto Sans CJK SC";font-weight:400;src:url("${staticFile('fonts/NotoSansCJKsc-Regular.otf')}")}
    @font-face {font-family:"Noto Sans CJK SC";font-weight:600 900;src:url("${staticFile('fonts/NotoSansCJKsc-Bold.otf')}")}
  `}</style>;
};
