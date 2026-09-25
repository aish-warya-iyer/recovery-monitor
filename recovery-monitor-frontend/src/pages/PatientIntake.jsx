import { useState } from 'react';
import { api } from '../api.js';
import { go } from '../hooks.js';
import AuthLayout from './AuthLayout.jsx';

const areas = [['knee', 'Knee'], ['shoulder_arm', 'Shoulder / arm'], ['back_core', 'Back / core'], ['hip', 'Hip'], ['general_mobility', 'General mobility']];
const issues = [['pain_during_movement', 'Pain during movement'], ['weakness', 'Weakness'], ['limited_range_of_motion', 'Limited range of motion'], ['balance_or_stability', 'Balance or stability'], ['difficulty_exercising', 'Difficulty exercising']];
const goals = [['improve_strength', 'Improve strength'], ['daily_activities', 'Daily activities'], ['general_conditioning', 'General conditioning']];
const toggle = (list, value) => list.includes(value) ? list.filter((item) => item !== value) : [...list, value];

export default function PatientIntake() {
  const [form, setForm] = useState({ affected_areas: [], issue_types: [], when_it_happens: ['during_movement'], pain_score: 0, duration: 'one_to_three_months', trend: 'unchanged', limitations: [], goals: [], notes: '' });
  const [state, setState] = useState({ saving: false, error: '' });
  const submit = async (event) => { event.preventDefault(); setState({ saving: true, error: '' }); try { await api.createIntake(form); go('/patient'); } catch (error) { setState({ saving: false, error: error.message }); } };
  const choose = (key, value) => setForm({ ...form, [key]: toggle(form[key], value) });
  return <AuthLayout eyebrow="Patient request" title="Tell a therapist what you need help with" subtitle="Your summary will be sent to therapists who can choose whether they can take on your care.">
    <form className="form auth-form" onSubmit={submit}>
      <fieldset className="choice-field"><legend>Area needing support</legend><div className="choice-grid">{areas.map(([v, l]) => <label className="check-card" key={v}><input type="checkbox" checked={form.affected_areas.includes(v)} onChange={() => choose('affected_areas', v)} />{l}</label>)}</div></fieldset>
      <fieldset className="choice-field"><legend>What are you experiencing?</legend><div className="choice-grid">{issues.map(([v, l]) => <label className="check-card" key={v}><input type="checkbox" checked={form.issue_types.includes(v)} onChange={() => choose('issue_types', v)} />{l}</label>)}</div></fieldset>
      <label className="field">Pain score: {form.pain_score}/10<input type="range" min="0" max="10" value={form.pain_score} onChange={(e) => setForm({ ...form, pain_score: Number(e.target.value) })} /></label>
      <label className="field">Additional notes<textarea rows="4" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} placeholder="Describe what you want a therapist to know" /></label>
      <fieldset className="choice-field"><legend>Your goal</legend><div className="choice-grid">{goals.map(([v, l]) => <label className="check-card" key={v}><input type="checkbox" checked={form.goals.includes(v)} onChange={() => choose('goals', v)} />{l}</label>)}</div></fieldset>
      {state.error && <p className="form-error">{state.error}</p>}
      <button className="primary-button" disabled={state.saving || !form.affected_areas.length || !form.issue_types.length || !form.goals.length}>{state.saving ? 'Sending request…' : 'Send therapist request'}</button>
    </form>
  </AuthLayout>;
}
