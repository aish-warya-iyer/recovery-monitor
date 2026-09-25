import { num } from '../hooks.js';
import { RepVerdict } from './ui.jsx';

// One compact row per rep; the selected rep opens to show the reasons, the models' opinions and the
// physio's correct/incorrect buttons (which override the model).
export default function RepList({ reps, onSelect, selected, labels, onLabel, physio = false, measure = 'Depth' }) {
  if (!reps?.length) return <div className="empty-note">No complete reps were detected.</div>;
  return (
    <div className="rep-list">
      {reps.map((r) => {
        const label = labels?.[r.index];
        const open = selected === r.index;
        const reasons = r.flag_reasons ?? [];
        return (
          <div key={r.index} role="button" tabIndex={0} aria-expanded={open}
            className={`rep-card ${open ? 'selected' : ''} ${r.predicted_correct ? '' : 'flagged'}`}
            onClick={() => onSelect?.(r)}
            onKeyDown={(e) => { if (e.target === e.currentTarget && (e.key === 'Enter' || e.key === ' ')) { e.preventDefault(); onSelect?.(r); } }}>
            <div className="rep-top">
              <strong>Rep {r.index}</strong>
              <span className="rep-inline">
                {num(r.peak_deg ?? r.min_knee_angle_deg, 0, '°')} · {num(r.duration_s, 1, ' s')}
              </span>
              {label ? (
                <span className={`badge ${label === 'correct' ? 'badge-green' : 'badge-amber'}`}>You: {label}</span>
              ) : <RepVerdict rep={r} />}
            </div>
            {!open && reasons.length > 0 && <p className="rep-teaser">{reasons[0].message}{reasons.length > 1 ? ` · +${reasons.length - 1} more` : ''}</p>}
            <div className="rep-detail" inert={!open}>
              <div className="rep-detail-inner">
                <div className="rep-metrics">
                  <span>{measure} <b>{num(r.peak_deg ?? r.min_knee_angle_deg, 0, '°')}</b></span>
                  <span>Time <b>{num(r.duration_s, 1, ' s')}</b></span>
                  {physio && r.probability_incorrect != null && (
                    <span>Model <b>{Math.round(r.probability_incorrect * 100)}%</b> off-form</span>
                  )}
                  {physio && r.vlm && r.vlm.correct !== null && (
                    <span>Video model: <b>{r.vlm.correct ? 'looks correct' : 'looks off'}</b></span>
                  )}
                </div>
                {reasons.length > 0 && (
                  <ul className="rep-reasons">
                    {reasons.slice(0, physio ? 4 : 2).map((f, i) => (
                      <li key={i} className={f.code === 'model_incorrect' ? 'model' : ''}>{f.message}</li>
                    ))}
                  </ul>
                )}
                {physio && (
                  <div className="rep-label" onClick={(e) => e.stopPropagation()}>
                    <span>Your call:</span>
                    <button className={label === 'correct' ? 'on good' : ''} onClick={() => onLabel(r.index, label === 'correct' ? null : 'correct')}>Correct</button>
                    <button className={label === 'incorrect' ? 'on bad' : ''} onClick={() => onLabel(r.index, label === 'incorrect' ? null : 'incorrect')}>Incorrect</button>
                  </div>
                )}
              </div>
            </div>
          </div>
        );
      })}
    </div>
  );
}
