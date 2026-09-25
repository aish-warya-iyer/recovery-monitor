import { useState } from 'react';
import { api } from '../api.js';
import { go } from '../hooks.js';
import AuthLayout from './AuthLayout.jsx';

export default function SignIn() {
  const [form, setForm] = useState({ email: '', password: '' });
  const [state, setState] = useState({ loading: false, error: '' });
  const submit = async (event) => {
    event.preventDefault(); setState({ loading: true, error: '' });
    try { const result = await api.authLogin(form); const user = result.user ?? result; go(result.onboarding_completed ? (user.role === 'therapist' ? '/physio' : `/patient/${user.id}`) : `/onboarding/${user.role}`); }
    catch (error) { setState({ loading: false, error: error.message }); }
  };
  return <AuthLayout eyebrow="Welcome back" title="Sign in to your care space" subtitle="Use your account to continue your recovery workflow.">
    <form className="form auth-form" onSubmit={submit}>
      <label className="field">Email<input type="email" required value={form.email} onChange={(e) => setForm({ ...form, email: e.target.value })} /></label>
      <label className="field">Password<input type="password" required minLength="6" value={form.password} onChange={(e) => setForm({ ...form, password: e.target.value })} /></label>
      {state.error && <p className="form-error">{state.error}</p>}
      <button className="primary-button" disabled={state.loading}>{state.loading ? 'Signing in…' : 'Sign in'}</button>
      <p className="auth-switch">New here? <button type="button" className="text-button" onClick={() => go('/signup')}>Create an account</button></p>
    </form>
  </AuthLayout>;
}
