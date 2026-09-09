import baseline from './evaluation-baseline.json';

export const EvaluationScene: React.FC = () => <div style={{position: 'absolute', top: 175, left: 135, right: 135}}>
  <div style={{fontSize: 38, color: '#1456b8', fontWeight: 700, marginBottom: 28}}>历史软件路径开发回归 ≠ 最终麒麟原生验收</div>
  <table style={{width: '100%', borderCollapse: 'collapse', background: '#fff', fontSize: 36}}>
    <thead><tr>{['指标', '赛题目标', '历史实测', '样本数', '最终 V11 双 SDK'].map((label) =>
      <th key={label} style={{textAlign: 'left', padding: '20px 18px', background: '#edf1f5', fontSize: 34}}>{label}</th>)}</tr></thead>
    <tbody>{baseline.metrics.map((m) => <tr key={m.name} style={{borderBottom: '2px solid #dce2ea'}}>
      <td style={{padding: '24px 18px'}}>{m.label}</td>
      <td>{m.comparison === '>=' ? '≥' : '≤'} {m.unit === 'ratio' ? `${m.target * 100}%` : `${m.target} 毫秒`}</td>
      <td style={{color: '#1456b8', fontWeight: 700}}>{m.unit === 'ratio' ? `${m.value * 100}%` : `${m.value.toFixed(3)} 毫秒`}</td>
      <td>{m.denominator}</td><td>同版评测待完成</td>
    </tr>)}</tbody>
  </table>
  <div style={{fontSize: 36, lineHeight: 1.6, color: '#526477', marginTop: 30}}>
    自建合成数据：50 组账单、15 个偏好用例、25 个冲突用例。<br />
    50 次检索各重复 20 次，共 1000 个延迟样本。<br />
    本轮另有 698 项基础设施回归通过，不替代以上质量指标。
  </div>
</div>;
