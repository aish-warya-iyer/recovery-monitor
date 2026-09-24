import { ChevronRight, Inbox } from 'lucide-react';
import { api } from '../api.js';
import { ErrorNote, FlagBadge, Initials, Panel } from '../components/ui.jsx';
import { fmtDateTime, go, usePoll } from '../hooks.js';

export default function PhysioQueue() {
  const queue = usePoll(() => api.reviewQueue(), 5000);
  const patients = usePoll(() => api.patients(), 15000);

  return (
    <div className="page">
      <header className="page-heading">
        <div>
          <span className="eyebrow">Physiotherapist</span>
          <h1>Review queue</h1>
          <p className="page-subtitle">Sessions the system flagged for you. Urgent (pain) first, then oldest.</p>
        </div>
      </header>
      <ErrorNote error={queue.error} />

      <Panel title={`${queue.data?.length ?? '—'} sessions waiting`}>
        {queue.data?.length === 0 && (
          <div className="empty-state"><Inbox size={22} /><p>Nothing to review. New flagged sessions appear here automatically.</p></div>
        )}
        <div className="queue">
          {queue.data?.map((s) => (
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

      <Panel title="Patients">
        <div className="patient-grid">
          {patients.data?.map((p) => (
            <button key={p.id} className="patient-card" onClick={() => go(`/physio/patient/${p.id}`)}>
              <Initials name={p.name} />
              <div>
                <strong>{p.name}</strong>
                <span>{p.protocol ? `${p.protocol.target_reps} squats to ${p.protocol.target_depth_deg}° · plan v${p.protocol.version}` : 'No plan yet'}</span>
                <span>Last session {fmtDateTime(p.last_session_at)} · {p.sessions_awaiting_review} awaiting review</span>
              </div>
            </button>
          ))}
        </div>
      </Panel>
    </div>
  );
}
