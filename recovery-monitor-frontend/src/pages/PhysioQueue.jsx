import { AlertCircle, ArrowRight, CheckCircle2, ChevronRight, Inbox, Users } from 'lucide-react';
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
      <header className="page-heading">
        <div>
          <span className="eyebrow">Care team workspace</span>
          <h1>Review queue</h1>
          <p className="page-subtitle">A focused view of the movement sessions that need your clinical attention.</p>
        </div>
        <span className="muted small">Updates automatically</span>
      </header>
      <ErrorNote error={queue.error || patients.error || intakes.error || decisionError} />
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
