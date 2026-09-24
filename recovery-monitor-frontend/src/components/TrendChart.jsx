import { fmtDate } from '../hooks.js';

const W = 960;
const H = 230;
const PAD = { l: 40, r: 40, t: 14, b: 30 };

// Recovery trend from real sessions: median squat depth (left axis, deeper = better, drawn upward)
// and pain (right axis). Sessions without a number are simply skipped, never invented.
export default function TrendChart({ sessions, targetDepth }) {
  const pts = (sessions || []).filter((s) => s.stage === 'done');
  if (pts.length < 2) {
    return <div className="empty-note">The trend appears after two analysed sessions.</div>;
  }
  const n = pts.length;
  const x = (i) => PAD.l + (i / (n - 1)) * (W - PAD.l - PAD.r);
  const depths = pts.map((s) => s.median_depth_deg).filter((v) => v != null);
  const dMax = Math.max(170, ...depths);
  const dMin = Math.min(targetDepth ?? 90, ...depths) - 10;
  const yD = (d) => PAD.t + ((d - dMin) / (dMax - dMin)) * (H - PAD.t - PAD.b); // deeper (smaller) -> higher
  const yP = (p) => PAD.t + ((10 - p) / 10) * (H - PAD.t - PAD.b);
  const line = (vals, y) =>
    vals.map((v, i) => (v == null ? null : `${x(i).toFixed(1)},${y(v).toFixed(1)}`)).filter(Boolean).join(' ');

  return (
    <div className="trend">
      <div className="legend">
        <span><i className="swatch depth" /> Median squat depth (knee angle, deeper is higher)</span>
        <span><i className="swatch pain" /> Pain (0–10)</span>
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="trend-chart" role="img" aria-label="Recovery trend">
        {targetDepth && (
          <g>
            <line x1={PAD.l} x2={W - PAD.r} y1={yD(targetDepth)} y2={yD(targetDepth)} className="target-line" />
            <text x={PAD.l + 4} y={yD(targetDepth) - 5} className="axis target-label">target {targetDepth}°</text>
          </g>
        )}
        <text x={PAD.l - 6} y={yD(dMin + 10) + 3} className="axis" textAnchor="end">{Math.round(dMin + 10)}°</text>
        <text x={PAD.l - 6} y={yD(dMax) + 3} className="axis" textAnchor="end">{Math.round(dMax)}°</text>
        <text x={W - PAD.r + 6} y={yP(10) + 3} className="axis">10</text>
        <text x={W - PAD.r + 6} y={yP(0) + 3} className="axis">0</text>
        <polyline points={line(pts.map((s) => s.median_depth_deg), yD)} className="trend-line depth" />
        <polyline points={line(pts.map((s) => s.pain_score), yP)} className="trend-line pain" />
        {pts.map((s, i) => (
          <g key={s.id}>
            {s.median_depth_deg != null && <circle cx={x(i)} cy={yD(s.median_depth_deg)} r="4.5" className="dot depth" />}
            {s.pain_score != null && <circle cx={x(i)} cy={yP(s.pain_score)} r="4" className="dot pain" />}
            <text x={x(i)} y={H - 8} className="axis" textAnchor="middle">{fmtDate(s.created_at)}</text>
          </g>
        ))}
      </svg>
    </div>
  );
}
