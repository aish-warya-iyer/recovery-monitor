import { api } from '../api.js';
import { ErrorNote, Note, Panel, Stat } from '../components/ui.jsx';
import { num, pct, useLoad } from '../hooks.js';

const VIEWS = [['side', 'Side'], ['half_profile', 'Half-profile (45°)'], ['front', 'Front']];

// Every number comes from /api/eval/summary (model/results/*.json). Missing numbers show "—".
export default function Evaluation() {
  const e = useLoad(() => api.evalSummary(), []);
  const d = e.data;
  const angle = d?.angle_accuracy;
  const reps = d?.rep_counting;
  const clf = d?.classifier;

  return (
    <div className="page">
      <header className="page-heading">
        <div>
          <span className="eyebrow">Evaluation</span>
          <h1>How accurate is it?</h1>
          <p className="page-subtitle">{d?.dataset ?? 'Measured on public data, on this device.'}</p>
        </div>
      </header>
      <ErrorNote error={e.error} />

      <Panel className="hero-panel">
        <div className="hero-number">
          <strong>±{num(angle?.per_frame?.side?.mae_deg, 1)}°</strong>
          <div>
            <h2>Knee angle vs. lab motion capture, filmed from the side</h2>
            <p>Mean absolute error over {angle?.per_frame?.side?.n?.toLocaleString() ?? '—'} video frames, compared with
              16-camera optical motion capture. Error in each rep's depth: ±{num(angle?.rep_depth?.side?.mae_deg, 1)}°.</p>
          </div>
        </div>
      </Panel>

      <div className="grid-3">
        <Panel title="Angle error by camera position" subtitle="Why the app asks you to film from the side">
          <table className="table compact">
            <thead><tr><th>View</th><th>Per frame</th><th>Rep depth</th></tr></thead>
            <tbody>
              {VIEWS.map(([k, label]) => (
                <tr key={k}><td>{label}</td><td>{num(angle?.per_frame?.[k]?.mae_deg, 1, '°')}</td><td>{num(angle?.rep_depth?.[k]?.mae_deg, 1, '°')}</td></tr>
              ))}
            </tbody>
          </table>
        </Panel>

        <Panel title="Rep counting" subtitle={`${reps?.overall?.gt_reps ?? '—'} expert-annotated reps`}>
          <div className="stats-row">
            <Stat label="Precision" value={pct(reps?.overall?.precision)} />
            <Stat label="Recall" value={pct(reps?.overall?.recall)} />
          </div>
          <table className="table compact">
            <thead><tr><th>View</th><th>Reps found</th></tr></thead>
            <tbody>
              {VIEWS.map(([k, label]) => (
                <tr key={k}><td>{label}</td><td>{pct(reps?.recall_by_view?.[k]?.recall)}</td></tr>
              ))}
            </tbody>
          </table>
        </Panel>

        <Panel title="Spotting incorrect reps" subtitle={clf?.evaluation}>
          <table className="table compact">
            <thead><tr><th></th><th>Caught</th><th>Precision</th><th>F1</th></tr></thead>
            <tbody>
              <tr><td>XGBoost vs patient baseline</td><td>{pct(clf?.xgboost?.recall_incorrect)}</td>
                <td>{pct(clf?.xgboost?.precision_incorrect)}</td><td>{num(clf?.xgboost?.f1_incorrect, 2)}</td></tr>
              <tr><td>Single-threshold rule</td><td>{pct(clf?.rules_baseline?.recall_incorrect)}</td>
                <td>{pct(clf?.rules_baseline?.precision_incorrect)}</td><td>{num(clf?.rules_baseline?.f1_incorrect, 2)}</td></tr>
            </tbody>
          </table>
          <p className="muted small">Tuned to catch most incorrect reps; the physio reviews every flag, so false alarms cost a
            click, not a missed problem. {clf?.n_reps ?? '—'} reps from {clf?.n_subjects ?? '—'} people, each person tested
            on a model that never saw them.</p>
        </Panel>
      </div>

      <Panel title="Limits we measured, not hid">
        <ul className="plain-list">{d?.caveats?.map((c) => <li key={c}>{c}</li>)}</ul>
        <Note>Not a medical device and not clinically validated. The physiotherapist makes every decision.</Note>
      </Panel>
    </div>
  );
}
