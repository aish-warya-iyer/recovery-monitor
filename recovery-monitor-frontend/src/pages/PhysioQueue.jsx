import { AlertCircle, ArrowRight, CheckCircle2, ChevronRight, Inbox, Users } from 'lucide-react';
import { useState } from 'react';
import { api } from '../api.js';
import { ErrorNote, FlagBadge, Initials, Panel } from '../components/ui.jsx';
import { fmtDateTime, go, usePoll } from '../hooks.js';

export default function PhysioQueue() {
  const queue = usePoll(() => api.reviewQueue(), 5000);
  const patients = usePoll(() => api.patients(), 15000);
  const [filter, setFilter] = useState('all');
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
      <header className="page-heading">
        <div>
          <span className="eyebrow">Care team workspace</span>
          <h1>Review queue</h1>
          <p className="page-subtitle">A focused view of the movement sessions that need your clinical attention.</p>
        </div>
        <span className="muted small">Updates automatically</span>
      </header>
      <ErrorNote error={queue.error || patients.error} />

      <section className="care-hero" aria-label="Care pulse">
        <div>
          <span className="eyebrow">Today’s care pulse</span>
          <h2>Keep every review moving.</h2>
          <p>Start with the sessions where movement evidence and patient-reported symptoms need your attention.</p>
        </div>
        <div className="care-hero-side">
          <span className="care-live-dot"><i /> Local analysis active</span>
          <strong>{urgentCount ? `${urgentCount} priority ${urgentCount === 1 ? 'session' : 'sessions'} first` : 'No priority flags'}</strong>
          <button className="care-hero-link" onClick={() => setFilter(urgentCount ? 'urgent' : 'all')}>
            {urgentCount ? 'Review priority sessions' : 'View all sessions'} <ArrowRight size={15} />
          </button>
        </div>
      </section>

      <section className="care-overview" aria-label="Care team overview">
        <div className="care-stat"><div className="care-stat-icon amber"><AlertCircle size={17} /></div><span>Needs attention</span><strong>{queue.data ? sessions.length : '—'}</strong><small>flagged sessions waiting</small></div>
        <div className="care-stat"><div className="care-stat-icon red"><AlertCircle size={17} /></div><span>Priority review</span><strong>{queue.data ? urgentCount : '—'}</strong><small>pain or urgent flags</small></div>
        <div className="care-stat"><div className="care-stat-icon blue"><Users size={17} /></div><span>Active patients</span><strong>{patients.data ? patientList.length : '—'}</strong><small>with care plans or sessions</small></div>
        <div className="care-stat"><div className="care-stat-icon green"><CheckCircle2 size={17} /></div><span>Workflow</span><strong>Review</strong><small>your decision stays final</small></div>
      </section>

      <Panel title={`${queue.data?.length ?? '—'} sessions waiting`} action={
        <div className="queue-filters" role="group" aria-label="Filter review queue">
          {[['all', 'All'], ['urgent', 'Priority'], ['form', 'Movement']].map(([value, label]) => (
            <button key={value} className={filter === value ? 'on' : ''} onClick={() => setFilter(value)}>{label}</button>
          ))}
        </div>
      }>
        {queue.data?.length === 0 && (
          <div className="empty-state"><Inbox size={22} /><p>Nothing to review. New flagged sessions appear here automatically.</p></div>
        )}
        {queue.data?.length > 0 && visibleSessions.length === 0 && (
          <div className="empty-state"><CheckCircle2 size={22} /><p>No sessions match this filter.</p></div>
        )}
        <div className="queue">
          {visibleSessions.map((s) => (
            <button key={s.id} className="queue-row" onClick={() => go(`/physio/session/${s.id}`)}>
              {s.thumbnail_url ? <img src={s.thumbnail_url} alt="" /> : <div className="thumb-empty" />}
              <div className="queue-main">
                <div className="queue-top">
                  <strong>{s.patient?.name}</strong>
                  <FlagBadge flag={s.flag} />
                  <span className="muted small">{fmtDateTime(s.created_at)}</span>
                </div>
                <ul className="reasons">{s.flag?.reasons.map((r) => <li key={r}>{r}</li>)}</ul>
              </div>
              <ChevronRight size={18} className="muted" />
            </button>
          ))}
        </div>
      </Panel>

      <Panel title="Patients" subtitle="Open a patient to review their trend and adjust their plan.">
        <div className="patient-grid">
          {patients.data?.map((p) => (
            <button key={p.id} className="patient-card" onClick={() => go(`/physio/patient/${p.id}`)}>
              <Initials name={p.name} />
              <div>
                <strong>{p.name}</strong>
                <span>{p.protocol ? `${p.protocol.target_reps} ${p.protocol.exercise === 'squat' ? 'squats' : 'repetitions'} · plan v${p.protocol.version}` : 'No plan yet'}</span>
                <span>Last session {fmtDateTime(p.last_session_at)} · {p.sessions_awaiting_review} awaiting review</span>
              </div>
            </button>
          ))}
        </div>
      </Panel>
    </div>
  );
}
