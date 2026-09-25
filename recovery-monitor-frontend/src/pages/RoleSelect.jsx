import { HeartPulse, ClipboardList } from 'lucide-react';
import { go } from '../hooks.js';
import AuthLayout from './AuthLayout.jsx';

export default function RoleSelect() {
  return <AuthLayout eyebrow="Your workspace" title="Choose your starting point" subtitle="The same evidence loop supports patients and therapists, with different next steps.">
    <div className="auth-choice-grid">
      <button className="auth-choice" onClick={() => go('/signup/patient')}><HeartPulse size={21} /><strong>Patient</strong><span>Describe what you are experiencing and build a therapist-reviewed plan.</span></button>
      <button className="auth-choice" onClick={() => go('/signup/therapist')}><ClipboardList size={21} /><strong>Therapist</strong><span>Review patient context and approve a safe, personalized exercise plan.</span></button>
    </div>
    <p className="auth-switch">Already have an account? <button className="text-button" onClick={() => go('/signin')}>Sign in</button></p>
  </AuthLayout>;
}
