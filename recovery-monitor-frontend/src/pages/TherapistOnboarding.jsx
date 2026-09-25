import { useState } from 'react';
import { api } from '../api.js';
import { go } from '../hooks.js';
import AuthLayout from './AuthLayout.jsx';
const specializations = [['lower_body', 'Lower body'], ['upper_body', 'Upper body'], ['general_mobility', 'General mobility']];
const exercises = [['squat', 'Squat'], ['leg_lunge', 'Leg lunge'], ['leg_abduction', 'Leg abduction'], ['arm_abduction', 'Arm abduction'], ['arm_vw', 'Arm V/W'], ['push_ups', 'Push-ups']];
const toggle = (list, value) => list.includes(value) ? list.filter((item) => item !== value) : [...list, value];
export default function TherapistOnboarding() {
  const [form, setForm] = useState({ name: '', specializations: [], supported_exercises: [] }); const [error, setError] = useState(''); const [loading, setLoading] = useState(false);
  const submit = async (event) => { event.preventDefault(); setLoading(true); setError(''); try { await api.therapistOnboarding(form); go('/physio'); } catch (e) { setError(e.message); setLoading(false); } };
  return <AuthLayout eyebrow="Therapist onboarding · 1 of 1" title="Set up your care profile" subtitle="This helps route the right patient context and exercise coverage to your review queue.">
    <form className="form auth-form" onSubmit={submit}><label className="field">Name<input required value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} /></label><fieldset className="choice-field"><legend>Your specialization</legend><div className="choice-grid">{specializations.map(([v, l]) => <label key={v} className="check-card"><input type="checkbox" checked={form.specializations.includes(v)} onChange={() => setForm({ ...form, specializations: toggle(form.specializations, v) })} />{l}</label>)}</div></fieldset><fieldset className="choice-field"><legend>Exercises you support</legend><div className="choice-grid">{exercises.map(([v, l]) => <label key={v} className="check-card"><input type="checkbox" checked={form.supported_exercises.includes(v)} onChange={() => setForm({ ...form, supported_exercises: toggle(form.supported_exercises, v) })} />{l}</label>)}</div></fieldset>{error && <p className="form-error">{error}</p>}<button className="primary-button" disabled={loading}>{loading ? 'Saving…' : 'Finish therapist profile'}</button></form>
  </AuthLayout>;
}
