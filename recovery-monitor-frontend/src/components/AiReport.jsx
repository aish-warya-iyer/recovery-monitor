import { BadgeCheck, RefreshCw, ShieldAlert, Sparkles } from 'lucide-react';
import { useState } from 'react';
import { api } from '../api.js';
import { Disclosure, ErrorNote, Note, Panel } from './ui.jsx';

export const AGREEMENT = {
  consistent: ['badge-green', 'Voice and video agree'],
  partly_consistent: ['badge-amber', 'Partly consistent'],
  inconsistent: ['badge-red', 'Voice and video disagree'],
  not_enough_info: ['badge-grey', 'Not enough to compare'],
};

// The local LLM's draft for the physiotherapist. Red flags come from fixed rules, not the LLM.
export default function AiReport({ session, onUpdated }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const r = session.report;

  async function regenerate() {
    setBusy(true);
    setError(null);
    try {
      await api.regenerateReport(session.id);
      onUpdated?.();
    } catch (e) {
      setError(e);
    }
    setBusy(false);
  }

  const action = (
    <button className="text-button" onClick={regenerate} disabled={busy}>
      <RefreshCw size={13} /> {busy ? 'Writing…' : r ? 'Regenerate' : 'Write report'}
    </button>
  );
  if (!r) {
    return (
      <Panel title="AI draft report" subtitle="Written on this device from the video results and what the patient said" action={action}>
        <p className="muted small">{busy ? 'The local model is writing the report…' : 'No report yet. It is written automatically after analysis and after the patient’s check-in.'}</p>
        <ErrorNote error={error} />
      </Panel>
    );
  }
  const [cls, label] = AGREEMENT[r.agreement] ?? AGREEMENT.not_enough_info;
  return (
    <Panel title="AI draft report" action={action} className="report-card"
      subtitle={r.source === 'llm' ? `${r.model} · written on this device` : 'Template (local model unavailable)'}>
      <div className="report-summary">
        <div className="report-chips">
          <span className={`badge ${cls}`}>{label}</span>
          {r.red_flags?.length > 0 && (
            <span className="badge badge-red"><ShieldAlert size={12} /> {r.red_flags.length} red flag{r.red_flags.length > 1 ? 's' : ''}</span>
          )}
          {r.checks?.numbers_verified && <span className="badge badge-grey"><BadgeCheck size={12} /> Numbers checked</span>}
        </div>
        <p className="report-headline"><Sparkles size={14} /> {r.suggested_next_step}</p>
      </div>

      <Disclosure label="View full report" openLabel="Hide full report" className="report-more">
        {r.red_flags?.length > 0 && (
          <Note tone="error">
            <strong>Red flags (fixed safety rules, not the AI)</strong>
            <ul>{r.red_flags.map((f) => <li key={f}>{f}</li>)}</ul>
          </Note>
        )}
        <div className="report">
          <section><h4>Patient said</h4><p>{r.patient_said}</p></section>
          <section><h4>Video showed</h4><p>{r.movement_summary}</p></section>
          <section><h4>Do they match?</h4><p>{r.agreement_note}</p></section>
          {r.concerns?.length > 0 && <section><h4>Concerns</h4><ul>{r.concerns.map((c) => <li key={c}>{c}</li>)}</ul></section>}
          {r.questions_for_patient?.length > 0 && (
            <section><h4>Questions you could ask</h4><ul>{r.questions_for_patient.map((c) => <li key={c}>{c}</li>)}</ul></section>
          )}
          {r.coaching_cues?.length > 0 && (
            <section><h4>Coaching cues</h4><ul>{r.coaching_cues.map((c) => <li key={c}>{c}</li>)}</ul></section>
          )}
          <section className="to-patient">
            <h4>Message to the patient</h4>
            <p>{r.patient_message}</p>
            <small className="muted">Only shown to the patient after you approve or request changes.</small>
          </section>
        </div>
      </Disclosure>
      <ErrorNote error={error} />
    </Panel>
  );
}
