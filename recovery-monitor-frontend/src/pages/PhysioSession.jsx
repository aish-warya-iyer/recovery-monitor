import { ArrowLeft, Check, Mic, RotateCcw } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { api } from '../api.js';
import AiReport, { AGREEMENT } from '../components/AiReport.jsx';
import RepList from '../components/RepList.jsx';
import { exerciseName } from '../exercises.js';
import SessionPlayer from '../components/SessionPlayer.jsx';
import { Disclosure, ErrorNote, FlagBadge, Note, Panel, Stat } from '../components/ui.jsx';
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

  const flaggedReps = r?.reps?.filter((x) => !x.predicted_correct).length ?? 0;
  const [agreeCls, agreeLabel] = s.report ? (AGREEMENT[s.report.agreement] ?? AGREEMENT.not_enough_info) : ['badge-grey', 'Report pending'];
  const reasons = s.flag?.reasons ?? [];

  return (
    <div className="page session-review">
      <button className="text-button back" onClick={() => go('/physio')}><ArrowLeft size={14} /> Review queue</button>
      <header className="page-heading">
        <div>
          <span className="eyebrow">Session review · {fmtDateTime(s.created_at)}</span>
          <h1>{patient.data?.name ?? s.patient_id}</h1>
          <p className="page-subtitle">{exerciseName(r?.exercise ?? s.exercise)}</p>
        </div>
        <FlagBadge flag={s.flag} />
      </header>

      <div className="glance">
        <div className="glance-tile">
          <span>Reps</span>
          <strong>{r ? r.repetitions : '—'}<small> / {r?.protocol?.target_reps ?? '—'}</small></strong>
        </div>
        <div className={`glance-tile ${flaggedReps ? 'amber' : 'green'}`}>
          <span>Need a look</span>
          <strong>{r ? flaggedReps : '—'}<small> rep{flaggedReps === 1 ? '' : 's'}</small></strong>
        </div>
        <div className={`glance-tile ${painHigh ? 'red' : ''}`}>
          <span>Pain</span>
          <strong>{s.check_in ? s.check_in.pain_score : '—'}<small> / 10</small></strong>
        </div>
        <div className="glance-tile">
          <span>Voice vs video</span>
          <span className={`badge ${agreeCls}`}>{agreeLabel}</span>
        </div>
      </div>

      {(reasons.length > 0 || r?.vlm?.mismatch) && (
        <Note tone={s.flag?.severity === 'urgent' ? 'error' : 'warn'}>
          <strong>{reasons[0] ?? 'Different exercise detected'}</strong>
          {reasons.length > 1 && <ul>{reasons.slice(1).map((x) => <li key={x}>{x}</li>)}</ul>}
          {r?.vlm?.mismatch && (
            <p className="note-line">The plan is <b>{exerciseName(r.vlm.planned_exercise).toLowerCase()}</b>, but our video model sees
              {' '}<b>{exerciseName(r.vlm.detected_exercise).toLowerCase()}</b>, so it was analysed as what was actually done.</p>
          )}
        </Note>
      )}

      <div className="review-layout">
        <div>
          <Panel title="Movement" subtitle="Click a rep or the chart to jump there · J / K next / previous rep">
            <SessionPlayer ref={player} session={s} selectedRep={selected} />
            {r && (
              <Disclosure label="Measurements and how this was analysed" openLabel="Hide measurements">
                <div className="stats-row">
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
                <ul className="method-list">
                  <li>{r.model?.classifier
                    ? `Compared with ${r.model.baseline_reps} approved reps from this patient's earlier sessions.`
                    : 'No approved baseline yet: video model and rules only.'}</li>
                  {r.vlm?.available && (
                    <li>Fine-tuned video model sees {exerciseName(r.vlm.detected_exercise).toLowerCase()} ({Math.round((r.vlm.confidence ?? 0) * 100)}% of
                      windows), camera {String(r.vlm.view ?? 'unknown').replace('_', ' ')}.</li>
                  )}
                </ul>
              </Disclosure>
            )}
          </Panel>

          <Panel title="Reps" subtitle="Select a rep to see why. Your call overrides the model and teaches future comparisons.">
            <RepList reps={r?.reps} physio measure={r?.exercise === 'squat' ? 'Depth' : (r?.measure_label ?? 'Peak')}
              selected={selected} onSelect={selectRep} labels={labels}
              onLabel={(i, v) => setLabels((l) => ({ ...l, [i]: v }))} />
          </Panel>
        </div>

        <div>
          <AiReport session={s} onUpdated={session.reload} />

          <Panel title="Patient check-in">
            {s.check_in ? (
              <div className="checkin">
                <div className="report-chips">
                  <span className={`badge ${painHigh ? 'badge-red' : 'badge-grey'}`}>Pain {s.check_in.pain_score}/10 · alert at {s.protocol?.pain_threshold ?? '—'}</span>
                  <span className="badge badge-grey">{s.check_in.stiffness ? 'Stiff' : 'No stiffness'}</span>
                </div>
                {s.check_in.transcript && <blockquote><Mic size={13} /> “{s.check_in.transcript}”</blockquote>}
                {s.check_in.comment && <blockquote>“{s.check_in.comment}”</blockquote>}
              </div>
            ) : <p className="muted small">No check-in yet.</p>}
          </Panel>

          <Panel title="Your decision" className="decision-panel">
            <label className="field">
              <span>Note to the patient</span>
              <textarea rows={2} value={notes} onChange={(e) => setNotes(e.target.value)}
                placeholder="e.g. Slow down on the way down and keep your knees behind your toes." />
            </label>
            <Disclosure label={refId ? 'Reference video attached' : 'Attach a reference video'} openLabel="Reference video">
              <select aria-label="Reference video to send" value={refId} onChange={(e) => setRefId(e.target.value ? Number(e.target.value) : '')}>
                <option value="">None</option>
                {refs.data?.map((v) => <option key={v.id} value={v.id}>{v.title}</option>)}
              </select>
            </Disclosure>
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
            <p className="muted small">
              {s.review && <>Last decision: {s.review.decision.replace('_', ' ')} on {fmtDateTime(s.review.created_at)}. </>}
              Approving adds these reps to the patient's baseline.
            </p>
          </Panel>
        </div>
      </div>
    </div>
  );
}
