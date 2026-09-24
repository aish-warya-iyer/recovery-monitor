import { useMemo, useRef } from 'react';

const W = 900;
const H = 220;
const PAD = { l: 44, r: 12, t: 12, b: 26 };
const A_MIN = 40;
const A_MAX = 185;

// Knee angle over time. Standing (~180°) at the top, deeper squats lower down, like the movement itself.
export default function AngleChart({ series, reps = [], targetDepth, currentTime = 0, onSeek, selectedRep }) {
  const ref = useRef(null);
  const duration = series?.t?.length ? series.t[series.t.length - 1] : 1;
  const x = (t) => PAD.l + (t / duration) * (W - PAD.l - PAD.r);
  const y = (a) => PAD.t + ((A_MAX - a) / (A_MAX - A_MIN)) * (H - PAD.t - PAD.b);

  const path = useMemo(() => {
    if (!series?.t) return '';
    let d = '';
    let pen = false;
    series.t.forEach((t, i) => {
      const a = series.knee[i];
      if (a === null || a === undefined) {
        pen = false;
        return;
      }
      d += `${pen ? 'L' : 'M'}${x(t).toFixed(1)},${y(Math.max(A_MIN, Math.min(A_MAX, a))).toFixed(1)}`;
      pen = true;
    });
    return d;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [series]);

  if (!series?.t?.length) return <div className="empty-note">No angle data for this session.</div>;

  const seek = (e) => {
    if (!onSeek) return;
    const box = ref.current.getBoundingClientRect();
    const px = ((e.clientX - box.left) / box.width) * W;
    onSeek(Math.max(0, Math.min(duration, ((px - PAD.l) / (W - PAD.l - PAD.r)) * duration)));
  };

  return (
    <svg ref={ref} className="angle-chart" viewBox={`0 0 ${W} ${H}`} onClick={seek} role="img"
      aria-label="Knee angle over time">
      {[180, 150, 120, 90, 60].map((a) => (
        <g key={a}>
          <line x1={PAD.l} x2={W - PAD.r} y1={y(a)} y2={y(a)} className="grid" />
          <text x={PAD.l - 8} y={y(a) + 3} className="axis" textAnchor="end">{a}°</text>
        </g>
      ))}
      {targetDepth && (
        <g>
          <rect x={PAD.l} width={W - PAD.l - PAD.r} y={y(targetDepth)} height={y(A_MIN) - y(targetDepth)}
            className="target-zone" />
          <line x1={PAD.l} x2={W - PAD.r} y1={y(targetDepth)} y2={y(targetDepth)} className="target-line" />
          <text x={W - PAD.r - 4} y={y(targetDepth) - 5} className="axis target-label" textAnchor="end">
            target depth {targetDepth}°
          </text>
        </g>
      )}
      {reps.map((r) => (
        <rect key={r.index} x={x(r.start_s)} width={Math.max(1, x(r.end_s) - x(r.start_s))} y={PAD.t}
          height={H - PAD.t - PAD.b}
          className={`rep-band ${r.predicted_correct ? '' : 'flagged'} ${selectedRep === r.index ? 'selected' : ''}`} />
      ))}
      <path d={path} className="knee-line" />
      {reps.map((r) => (
        <text key={`l${r.index}`} x={(x(r.start_s) + x(r.end_s)) / 2} y={H - 8} className="axis rep-label"
          textAnchor="middle">{r.index}</text>
      ))}
      <line x1={x(currentTime)} x2={x(currentTime)} y1={PAD.t} y2={H - PAD.b} className="cursor" />
    </svg>
  );
}
