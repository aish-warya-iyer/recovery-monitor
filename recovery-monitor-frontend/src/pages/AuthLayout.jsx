import { Activity, ArrowLeft } from 'lucide-react';
import { go } from '../hooks.js';

export default function AuthLayout({ eyebrow, title, subtitle, children }) {
  return <div className="auth-page">
    <button className="auth-back" onClick={() => go('/')}><ArrowLeft size={15} /> Back to home</button>
    <div className="auth-brand"><span className="brand-mark"><Activity size={18} /></span><span><strong>Recovery Monitor</strong><small>On-device rehab evidence</small></span></div>
    <section className="auth-card"><span className="eyebrow">{eyebrow}</span><h1>{title}</h1><p className="page-subtitle">{subtitle}</p>{children}</section>
  </div>;
}
