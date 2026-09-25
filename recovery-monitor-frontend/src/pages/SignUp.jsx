import { useState } from 'react';
import { api } from '../api.js';
import { go, useRoute } from '../hooks.js';
import AuthLayout from './AuthLayout.jsx';

export default function SignUp() {
  const [, selectedRole] = useRoute();
  const [form, setForm] = useState({ email: '', password: '', role: selectedRole === 'therapist' ? 'therapist' : 'patient' });
  const [state, setState] = useState({ loading: false, error: '' });
  const submit = async (event) => {
    event.preventDefault(); setState({ loading: true, error: '' });
    try { const result = await api.authSignup(form); const user = result.user ?? result; go(`/onboarding/${user.role}`); }
    catch (error) { setState({ loading: false, error: error.message }); }
  };
  return <AuthLayout eyebrow="Start simply" title="Create your account" subtitle="Choose the space that matches your role. You can complete a short profile next.">
    <form className="form auth-form" onSubmit={submit}>
      <label className="field">Email<input type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></label>
      <label className="field">Password<input type="password" required minLength="6" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></label>
      <div className="field">I am a
        <div className="choice-row">{[['patient', 'Patient'], ['therapist', 'Therapist']].map(([value, label]) => <button type="button" key={value} className={`choice-button ${form.role === value ? 'selected' : ''}`} onClick={() => setForm({ ...form, role: value })}>{label}</button>)}</div>
      </div>
      {state.error && <p className="form-error">{state.error}</p>}
      <button className="primary-button" disabled={state.loading}>{state.loading ? 'Creating…' : 'Create account'}</button>
      <p className="auth-switch">Already registered? <button type="button" className="text-button" onClick={() => go('/signin')}>Sign in</button></p>
    </form>
  </AuthLayout>;
}
