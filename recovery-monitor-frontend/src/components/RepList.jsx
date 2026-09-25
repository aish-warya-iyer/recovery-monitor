import { num } from '../hooks.js';
import { RepVerdict } from './ui.jsx';

// One card per rep. Physio mode adds correct/incorrect buttons that override the model.
export default function RepList({ reps, onSelect, selected, labels, onLabel, physio = false, measure = 'Depth' }) {
  if (!reps?.length) return <div className="empty-note">No complete reps were detected.</div>;
  return (
    <div className="rep-list">
      {reps.map((r) => {
        const label = labels?.[r.index];
        return (
          <div key={r.index} className={`rep-card ${selected === r.index ? 'selected' : ''} ${r.predicted_correct ? '' : 'flagged'}`}
            onClick={() => onSelect?.(r)}>
            <div className="rep-top">
              <strong>Rep {r.index}</strong>
              <RepVerdict rep={r} />
            </div>
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
            {r.flag_reasons?.length > 0 && (
              <ul className="rep-reasons">
                {r.flag_reasons.slice(0, physio ? 4 : 2).map((f, i) => (
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
        );
      })}
    </div>
  );
}
