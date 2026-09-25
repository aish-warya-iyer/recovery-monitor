import { ArrowLeft, Check, RotateCcw } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { api } from '../api.js';
import AiReport from '../components/AiReport.jsx';
import RepList from '../components/RepList.jsx';
import { exerciseName } from '../exercises.js';
import SessionPlayer from '../components/SessionPlayer.jsx';
import { ErrorNote, FlagBadge, Note, Panel, Stat } from '../components/ui.jsx';
import { fmtDateTime, go, num, pct, useLoad } from '../hooks.js';

export default function PhysioSession({ sessionId }) {
  const session = useLoad(() => api.session(sessionId), [sessionId]);
  const refs = useLoad(() => api.referenceVideos(), []);
  const player = useRef(null);
  const [selected, setSelected] = useState(null);
  const [labels, setLabels] = useState({});
  const [notes, setNotes] = useState('');
  const [refId, setRefId] = useState('');
  const [ackPain, setAckPain] = useState(false);
  const [submit, setSubmit] = useState({ saving: false, error: null });

  const s = session.data;
  const r = s?.result;
  const patient = useLoad(() => (s ? api.patient(s.patient_id) : Promise.resolve(null)), [s?.patient_id]);

  useEffect(() => {
    if (s?.review) {
      setLabels(s.review.rep_labels || {});
      setNotes(s.review.notes || '');
      setRefId(s.review.reference_video_id ?? '');
    } else if (s?.protocol?.reference_video_id) {
      setRefId(s.protocol.reference_video_id);
    }
  }, [s?.id]); // eslint-disable-line react-hooks/exhaustive-deps

  // J / K to move between reps: quick review with the keyboard.
  useEffect(() => {
    const onKey = (e) => {
      if (!r?.reps?.length || ['TEXTAREA', 'INPUT', 'SELECT'].includes(e.target.tagName)) return;
      const i = r.reps.findIndex((x) => x.index === selected);
      const next = e.key === 'j' ? r.reps[Math.min(r.reps.length - 1, i + 1)] : e.key === 'k' ? r.reps[Math.max(0, i - 1)] : null;
      if (next) selectRep(next);
    };
    window.addEventListener('keydown', onKey);
    return () => window.removeEventListener('keydown', onKey);
  });

  function selectRep(rep) {
    setSelected(rep.index);
    player.current?.seek(rep.start_s);
  }

  const painHigh = s?.check_in && s.protocol && s.check_in.pain_score >= s.protocol.pain_threshold;

  async function decide(decision) {
    setSubmit({ saving: true, error: null });
    try {
      const clean = Object.fromEntries(Object.entries(labels).filter(([, v]) => v));
      await api.review(sessionId, {
        decision, notes, rep_labels: clean, reference_video_id: refId || null, acknowledge_pain: ackPain,
      });
      go('/physio');
    } catch (error) {
      setSubmit({ saving: false, error });
    }
  }

  if (session.error) return <div className="page"><ErrorNote error={session.error} /></div>;
  if (!s) return <div className="page"><p className="muted">Loading…</p></div>;

  return (
    <div className="page">
      <button className="text-button back" onClick={() => go('/physio')}><ArrowLeft size={14} /> Review queue</button>
      <header className="page-heading">
        <div>
          <span className="eyebrow">Session review</span>
          <h1>{patient.data?.name ?? s.patient_id} · {fmtDateTime(s.created_at)}</h1>
          <p className="page-subtitle">
            {exerciseName(r?.exercise ?? s.exercise)} · {r?.model?.classifier
              ? `compared with ${r.model.baseline_reps} approved reps from earlier sessions`
              : 'no approved baseline yet: video model and rules only'}
          </p>
        </div>
        <FlagBadge flag={s.flag} />
      </header>

      {s.flag?.reasons?.length > 0 && (
        <Note tone={s.flag.severity === 'urgent' ? 'error' : 'warn'}>
          <strong>Why this was flagged</strong>
          <ul>{s.flag.reasons.map((x) => <li key={x}>{x}</li>)}</ul>
        </Note>
      )}

      {r?.vlm?.available && (
        <Note tone={r.vlm.mismatch ? 'warn' : 'info'}>
          Our fine-tuned video model sees <strong>{exerciseName(r.vlm.detected_exercise).toLowerCase()}</strong>
          {' '}({Math.round((r.vlm.confidence ?? 0) * 100)}% of windows), camera {String(r.vlm.view ?? 'unknown').replace('_', ' ')}.
          {r.vlm.mismatch && <> The plan is <strong>{exerciseName(r.vlm.planned_exercise).toLowerCase()}</strong>, so this was analysed as what was actually done.</>}
        </Note>
      )}

      <div className="review-layout">
        <div>
          <Panel title="Movement" subtitle="Click a rep or the chart to jump there · J / K for next / previous rep">
            <SessionPlayer ref={player} session={s} selectedRep={selected} />
          </Panel>
          {r && (
            <Panel title="Session numbers">
              <div className="stats-row">
                <Stat label="Reps" value={`${r.repetitions} / ${r.protocol?.target_reps ?? '—'}`} />
                {r.exercise === 'squat' || !r.exercise ? (
                  <>
                    <Stat label="Reached target depth" value={`${r.metrics?.reps_reaching_target ?? 0}`} sub={`target ${r.protocol?.target_depth_deg ?? '—'}°`} />
                    <Stat label="Median depth" value={num(r.metrics?.median_depth_deg, 0, '°')} />
                  </>
                ) : (
                  <>
                    <Stat label={r.measure_label ?? 'Peak'} value={num(r.metrics?.peak_deg, 0, '°')} sub="best rep" />
                    <Stat label="Median range" value={num(r.metrics?.median_range_deg, 0, '°')} />
                  </>
                )}
                <Stat label="Tracking confidence" value={pct(r.confidence)} sub={`camera: ${r.quality?.view?.replace('_', ' ') ?? '—'}`} />
              </div>
            </Panel>
          )}
        </div>

        <div>
          <Panel title="Reps" subtitle="The model's view; your call overrides it and teaches future comparisons">
            <RepList reps={r?.reps} physio measure={r?.exercise === 'squat' ? 'Depth' : (r?.measure_label ?? 'Peak')}
              selected={selected} onSelect={selectRep} labels={labels}
              onLabel={(i, v) => setLabels((l) => ({ ...l, [i]: v }))} />
          </Panel>

          <AiReport session={s} onUpdated={session.reload} />

          <Panel title="Patient check-in">
            {s.check_in ? (
              <>
                <div className="stats-row">
                  <Stat label="Pain" value={`${s.check_in.pain_score}/10`} tone={painHigh ? 'red' : ''}
                    sub={`plan threshold ${s.protocol?.pain_threshold ?? '—'}`} />
                  <Stat label="Stiffness" value={s.check_in.stiffness ? 'Yes' : 'No'} />
                </div>
                {s.check_in.transcript && <blockquote>🎤 “{s.check_in.transcript}”</blockquote>}
                {s.check_in.comment && <blockquote>“{s.check_in.comment}”</blockquote>}
              </>
            ) : <p className="muted small">No check-in yet.</p>}
          </Panel>

          <Panel title="Your decision">
            <label className="field">
              <span>Note to the patient</span>
              <textarea rows={3} value={notes} onChange={(e) => setNotes(e.target.value)}
                placeholder="e.g. Slow down on the way down and keep your knees behind your toes." />
            </label>
            <label className="field">
              <span>Reference video to send</span>
              <select value={refId} onChange={(e) => setRefId(e.target.value ? Number(e.target.value) : '')}>
                <option value="">None</option>
                {refs.data?.map((v) => <option key={v.id} value={v.id}>{v.title}</option>)}
              </select>
            </label>
            {painHigh && (
              <label className="check warn">
                <input type="checkbox" checked={ackPain} onChange={(e) => setAckPain(e.target.checked)} />
                I reviewed the pain report ({s.check_in.pain_score}/10) before approving
              </label>
            )}
            <div className="decision-actions">
              <button className="secondary-button" disabled={submit.saving} onClick={() => decide('request_changes')}>
                <RotateCcw size={14} /> Request changes
              </button>
              <button className="primary-button success" disabled={submit.saving || (painHigh && !ackPain)} onClick={() => decide('approve')}>
                <Check size={14} /> Approve
              </button>
            </div>
            <ErrorNote error={submit.error} />
            {s.review && <p className="muted small">Last decision: {s.review.decision.replace('_', ' ')} on {fmtDateTime(s.review.created_at)}</p>}
            <p className="muted small">Approving makes this session's reps part of the patient's baseline for future comparisons.</p>
          </Panel>
        </div>
      </div>
    </div>
  );
}
