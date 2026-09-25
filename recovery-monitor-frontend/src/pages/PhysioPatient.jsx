import { ArrowLeft, Save } from 'lucide-react';
import { useEffect, useState } from 'react';
import { api } from '../api.js';
import TrendChart from '../components/TrendChart.jsx';
import { ErrorNote, FlagBadge, Note, Panel } from '../components/ui.jsx';
import { EXERCISES } from '../exercises.js';
import { fmtDateTime, go, num, useLoad } from '../hooks.js';

export default function PhysioPatient({ patientId }) {
  const patient = useLoad(() => api.patient(patientId), [patientId]);
  const history = useLoad(() => api.patientSessions(patientId), [patientId]);
  const refs = useLoad(() => api.referenceVideos(), []);
  const protocol = patient.data?.protocol;

  return (
    <div className="page">
      <button className="text-button back" onClick={() => go('/physio')}><ArrowLeft size={14} /> Review queue</button>
      <header className="page-heading">
        <div>
          <span className="eyebrow">Patient</span>
          <h1>{patient.data?.name}</h1>
          <p className="page-subtitle">{patient.data?.condition}</p>
        </div>
      </header>
      <ErrorNote error={patient.error} />

      <div className="grid-2">
        <Panel title="Recovery trend">
          <TrendChart sessions={history.data} targetDepth={protocol?.target_depth_deg} />
        </Panel>
        <Panel title="Exercise plan" subtitle={protocol ? `Version ${protocol.version} · ${fmtDateTime(protocol.created_at)}` : 'No plan yet'}>
          <ProtocolEditor patientId={patientId} protocol={protocol} refs={refs.data} onSaved={patient.reload} />
        </Panel>
      </div>

      <Panel title="Sessions">
        <table className="table">
          <thead><tr><th>Date</th><th>Reps</th><th>Flagged reps</th><th>Median depth</th><th>Pain</th><th>Status</th><th>Decision</th></tr></thead>
          <tbody>
            {history.data?.slice().reverse().map((s) => (
              <tr key={s.id} onClick={() => go(`/physio/session/${s.id}`)}>
                <td>{fmtDateTime(s.created_at)}</td>
                <td>{num(s.repetitions)}</td>
                <td>{s.repetitions != null ? s.repetitions - (s.correct_repetitions ?? 0) : '—'}</td>
                <td>{num(s.median_depth_deg, 0, '°')}</td>
                <td>{s.pain_score ?? '—'}</td>
                <td><FlagBadge flag={s.flag} /></td>
                <td>{s.review ? s.review.decision.replace('_', ' ') : 'pending'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Panel>
    </div>
  );
}

function ProtocolEditor({ patientId, protocol, refs, onSaved }) {
  const blank = { exercise: 'squat', target_reps: 10, target_depth_deg: 100, pain_threshold: 5, tempo: '', notes: '', reference_video_id: null };
  const [form, setForm] = useState(blank);
  const [state, setState] = useState({ saving: false, error: null, saved: false });
  useEffect(() => {
    if (protocol) setForm({ ...blank, ...protocol });
  }, [protocol?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.type === 'number' ? Number(e.target.value) : e.target.value }));

  async function save() {
    setState({ saving: true, error: null, saved: false });
    try {
      await api.setProtocol(patientId, {
        exercise: form.exercise, target_reps: form.target_reps, target_depth_deg: form.target_depth_deg,
        pain_threshold: form.pain_threshold, tempo: form.tempo || null, notes: form.notes || null,
        reference_video_id: form.reference_video_id ? Number(form.reference_video_id) : null,
      });
      setState({ saving: false, error: null, saved: true });
      onSaved();
    } catch (error) {
      setState({ saving: false, error, saved: false });
    }
  }

  return (
    <div className="form">
      <label className="field">
        <span>Exercise</span>
        <select value={form.exercise} onChange={set('exercise')}>
          {Object.entries(EXERCISES).filter(([k]) => k !== 'seated_leg_extension').map(([k, v]) => (
            <option key={k} value={k}>{v.name} · {v.area}</option>
          ))}
        </select>
      </label>
      <div className="form-row">
        <label className="field"><span>Repetitions</span><input type="number" min="1" max="100" value={form.target_reps} onChange={set('target_reps')} /></label>
        <label className="field"><span>Target depth (knee °)</span><input type="number" min="30" max="175" value={form.target_depth_deg} onChange={set('target_depth_deg')} /></label>
        <label className="field"><span>Pain alert at</span><input type="number" min="0" max="10" value={form.pain_threshold} onChange={set('pain_threshold')} /></label>
      </div>
      <label className="field"><span>Tempo</span><input value={form.tempo ?? ''} onChange={set('tempo')} placeholder="Slow and controlled, 2 s down" /></label>
      <label className="field"><span>Notes for the patient</span><textarea rows={2} value={form.notes ?? ''} onChange={set('notes')} /></label>
      <label className="field">
        <span>Reference video</span>
        <select value={form.reference_video_id ?? ''} onChange={set('reference_video_id')}>
          <option value="">None</option>
          {refs?.map((v) => <option key={v.id} value={v.id}>{v.title}</option>)}
        </select>
      </label>
      <Note>Smaller knee angle = deeper squat. Saving creates a new plan version; earlier sessions keep the plan they were done under.</Note>
      <button className="primary-button" onClick={save} disabled={state.saving}><Save size={14} /> {state.saving ? 'Saving…' : 'Save new plan version'}</button>
      {state.saved && <Note tone="ok">Saved. The patient sees the new plan next time they open the app.</Note>}
      <ErrorNote error={state.error} />
    </div>
  );
}
