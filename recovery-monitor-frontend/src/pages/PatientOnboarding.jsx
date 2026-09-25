import { useState } from 'react';
import { api } from '../api.js';
import { go } from '../hooks.js';
import AuthLayout from './AuthLayout.jsx';

const areas = [['knee', 'Knee'], ['shoulder_arm', 'Shoulder / arm'], ['back_core', 'Back / core'], ['hip', 'Hip'], ['ankle_foot', 'Ankle / foot'], ['general_mobility', 'General mobility']];
const goals = [['improve_strength', 'Improve strength'], ['daily_activities', 'Daily activities'], ['range_of_motion', 'Range of motion'], ['confidence_moving', 'Confidence moving']];
const toggle = (list, value) => list.includes(value) ? list.filter((item) => item !== value) : [...list, value];
export default function PatientOnboarding() {
  const [form, setForm] = useState({ name: '', affected_areas: [], goals: [], consent_local_analysis: false }); const [error, setError] = useState(''); const [loading, setLoading] = useState(false);
  const submit = async (event) => { event.preventDefault(); setLoading(true); setError(''); try { const result = await api.patientOnboarding(form); go(`/patient/${result.user?.id ?? 'jordan'}`); } catch (e) { setError(e.message); setLoading(false); } };
  return <AuthLayout eyebrow="Patient onboarding · 1 of 1" title="Tell us a little about you" subtitle="These choices help the care team understand your starting point. They are not a diagnosis.">
    <form className="form auth-form" onSubmit={submit}><label className="field">Name<input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label><fieldset className="choice-field"><legend>Where would you like support?</legend><div className="choice-grid">{areas.map(([v, l]) => <label key={v} className="check-card"><input type="checkbox" checked={form.affected_areas.includes(v)} onChange={() => setForm({ ...form, affected_areas: toggle(form.affected_areas, v) })} />{l}</label>)}</div></fieldset><fieldset className="choice-field"><legend>What is your goal?</legend><div className="choice-grid">{goals.map(([v, l]) => <label key={v} className="check-card"><input type="checkbox" checked={form.goals.includes(v)} onChange={() => setForm({ ...form, goals: toggle(form.goals, v) })} />{l}</label>)}</div></fieldset><label className="consent"><input type="checkbox" required checked={form.consent_local_analysis} onChange={(e) => setForm({ ...form, consent_local_analysis: e.target.checked })} /> I understand movement analysis runs locally on this device.</label>{error && <p className="form-error">{error}</p>}<button className="primary-button" disabled={loading}>{loading ? 'Saving…' : 'Finish patient profile'}</button></form>
  </AuthLayout>;
}
