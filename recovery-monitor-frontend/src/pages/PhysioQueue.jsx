import { AlertCircle, CheckCircle2, ChevronRight, Inbox, Play, Users } from 'lucide-react';
import { useState } from 'react';
import { api } from '../api.js';
import { exerciseName } from '../exercises.js';
import { ErrorNote, FlagBadge, Initials, Panel } from '../components/ui.jsx';
import { fmtDateTime, go, usePoll } from '../hooks.js';

export default function PhysioQueue() {
  const queue = usePoll(() => api.reviewQueue(), 5000);
  const patients = usePoll(() => api.patients(), 15000);
  const intakes = usePoll(() => api.therapistIntakes(), 10000);
  const [filter, setFilter] = useState('all');
  const [decisionError, setDecisionError] = useState(null);
  const sessions = queue.data ?? [];
  const patientList = patients.data ?? [];
  const urgentCount = sessions.filter((s) => s.flag?.severity === 'urgent').length;
  const visibleSessions = filter === 'urgent'
    ? sessions.filter((s) => s.flag?.severity === 'urgent')
    : filter === 'form'
      ? sessions.filter((s) => s.flag?.severity !== 'urgent')
      : sessions;

  return (
    <div className="page care-dashboard">
      <header className="page-heading queue-hero">
        <div>
          <span className="eyebrow">{new Date().toLocaleDateString(undefined, { weekday: 'long', month: 'long', day: 'numeric' })}</span>
          <h1>Review queue</h1>
          <p className="page-subtitle">Sessions the on-device models flagged for your attention. Urgent first.</p>
        </div>
        <span className="chip"><span className="status-dot" style={{ color: '#34c759' }} /> Updates live</span>
      </header>
      <ErrorNote error={queue.error || patients.error || intakes.error || decisionError} />

      <section className="care-overview" aria-label="Overview">
        <div className="care-stat"><div className="care-stat-icon amber"><AlertCircle size={17} /></div><span>Waiting for review</span><strong>{queue.data ? sessions.length : '—'}</strong><small>flagged sessions</small></div>
        <div className="care-stat"><div className="care-stat-icon red"><AlertCircle size={17} /></div><span>Urgent</span><strong>{queue.data ? urgentCount : '—'}</strong><small>pain or red-flag words</small></div>
        <div className="care-stat"><div className="care-stat-icon blue"><Users size={17} /></div><span>Your patients</span><strong>{patients.data ? patientList.length : '—'}</strong><small>with a plan or sessions</small></div>
        <div className="care-stat"><div className="care-stat-icon green"><Inbox size={17} /></div><span>New requests</span><strong>{intakes.data ? intakes.data.length : '—'}</strong><small>patients asking for care</small></div>
      </section>

      <Panel title={`${queue.data?.length ?? '—'} sessions waiting`} action={
        <div className="queue-filters" role="group" aria-label="Filter review queue">
          {[['all', 'All'], ['urgent', 'Urgent'], ['form', 'Movement']].map(([value, label]) => (
            <button key={value} className={filter === value ? 'on' : ''} aria-pressed={filter === value} onClick={() => setFilter(value)}>{label}</button>
          ))}
        </div>
      }>
        {queue.data?.length === 0 && (
          <div className="empty-state"><CheckCircle2 size={24} /><p>All caught up. New flagged sessions appear here automatically.</p></div>
        )}
        {queue.data?.length > 0 && visibleSessions.length === 0 && (
          <div className="empty-state"><CheckCircle2 size={22} /><p>No sessions match this filter.</p></div>
        )}
        <div className="queue">
          {visibleSessions.map((s) => (
            <button key={s.id} className={`queue-row ${s.flag?.severity === 'urgent' ? 'urgent' : ''}`} onClick={() => go(`/physio/session/${s.id}`)}>
              <span className="queue-thumb">
                {s.thumbnail_url ? <img src={s.thumbnail_url} alt="" /> : <span className="thumb-empty" />}
                <span className="play"><Play size={13} fill="currentColor" /></span>
              </span>
              <div className="queue-main">
                <div className="queue-top">
                  <strong>{s.patient?.name ?? s.patient_id}</strong>
                  <FlagBadge flag={s.flag} />
                </div>
                <div className="queue-sub">
                  {exerciseName(s.exercise)} · {s.repetitions ?? '—'} reps{s.pain_score != null ? ` · pain ${s.pain_score}/10` : ''} · {fmtDateTime(s.created_at)}
                </div>
                {s.flag?.reasons?.length > 0 && <ul className="reasons">{s.flag.reasons.slice(0, 3).map((x) => <li key={x}>{x}</li>)}</ul>}
              </div>
              <ChevronRight size={18} className="muted" />
            </button>
          ))}
        </div>
      </Panel>

      <Panel title="Patient requests" subtitle="Choose which patients you want to take on.">
        {intakes.data?.length ? <div className="intake-request-list">{intakes.data.map((intake) => <div className="intake-request" key={intake.id}><div><strong>{intake.patient?.name || intake.patient?.email || intake.patient_user_id}</strong><span>{intake.affected_areas?.join(', ')} · {intake.status}</span><small>{intake.notes || 'New patient care request'}</small></div><div className="intake-actions"><button className="primary-button" onClick={async () => { try { await api.claimIntake(intake.id); intakes.reload(); } catch (e) { setDecisionError(e); } }}>Accept patient</button><button className="secondary-button" onClick={async () => { try { await api.declineIntake(intake.id); intakes.reload(); } catch (e) { setDecisionError(e); } }}>Decline</button></div></div>)}</div> : <div className="empty-state intake-empty"><Inbox size={22} /><p>No patient requests yet.</p><small>When a patient submits an issue intake, it will appear here for you to accept or decline.</small></div>}
      </Panel>

      <Panel title="Patients" subtitle="Open a patient to review their trend and adjust their plan.">
        <div className="patient-grid">
          {patients.data?.map((p) => (
            <button key={p.id} className="patient-card" onClick={() => go(`/physio/patient/${p.id}`)}>
              <Initials name={p.name} />
              <div>
                <strong>{p.name}</strong>
                <span>{p.protocol ? `${p.protocol.target_reps} × ${exerciseName(p.protocol.exercise).toLowerCase()} · plan v${p.protocol.version}` : 'No plan yet'}</span>
                <span>Last session {fmtDateTime(p.last_session_at)} · {p.sessions_awaiting_review} awaiting review</span>
              </div>
            </button>
          ))}
        </div>
      </Panel>
    </div>
  );
}
