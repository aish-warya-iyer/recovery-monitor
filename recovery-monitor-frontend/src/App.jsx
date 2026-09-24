import { Activity, BarChart3, ClipboardList, HeartPulse, LockKeyhole, UserRound, Wifi, WifiOff } from 'lucide-react';
import { api } from './api.js';
import { Initials } from './components/ui.jsx';
import { go, useLoad, usePoll, useRoute } from './hooks.js';
import Evaluation from './pages/Evaluation.jsx';
import PatientHome from './pages/PatientHome.jsx';
import PhysioPatient from './pages/PhysioPatient.jsx';
import PhysioQueue from './pages/PhysioQueue.jsx';
import PhysioSession from './pages/PhysioSession.jsx';
import Privacy from './pages/Privacy.jsx';

export default function App() {
  const route = useRoute();
  const [area, a, b] = route;
  const health = usePoll(() => api.health(), 5000);
  const queue = usePoll(() => (area === 'physio' ? api.reviewQueue() : Promise.resolve(null)), 10000, [area]);

  let page;
  if (area === 'patient' && a) page = <PatientHome key={a} patientId={a} />;
  else if (area === 'physio' && a === 'session' && b) page = <PhysioSession key={b} sessionId={b} />;
  else if (area === 'physio' && a === 'patient' && b) page = <PhysioPatient key={b} patientId={b} />;
  else if (area === 'physio') page = <PhysioQueue />;
  else if (area === 'evaluation') page = <Evaluation />;
  else if (area === 'privacy') page = <Privacy />;
  else page = <RolePicker />;

  const nav = area === 'patient'
    ? [[`/patient/${a}`, 'My sessions', HeartPulse, true]]
    : area === 'physio'
      ? [['/physio', 'Review queue', ClipboardList, !a, queue.data?.length]]
      : [];
  const h = health.data;

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <button className="brand" onClick={() => go('/')}>
          <span className="brand-mark"><Activity size={18} /></span>
          <span><strong>Recovery Monitor</strong><small>On-device rehab evidence</small></span>
        </button>
        {nav.length > 0 && <div className="nav-label">{area === 'patient' ? 'Patient' : 'Physiotherapist'}</div>}
        <nav className="nav-list">
          {nav.map(([path, label, Icon, active, count]) => (
            <button key={path} className={`nav-item ${active ? 'active' : ''}`} onClick={() => go(path)}>
              <Icon size={15} /> {label} {count ? <span className="nav-count">{count}</span> : null}
            </button>
          ))}
        </nav>
        <div className="nav-label lower">About this system</div>
        <nav className="nav-list">
          <button className={`nav-item ${area === 'evaluation' ? 'active' : ''}`} onClick={() => go('/evaluation')}><BarChart3 size={15} /> Accuracy</button>
          <button className={`nav-item ${area === 'privacy' ? 'active' : ''}`} onClick={() => go('/privacy')}><LockKeyhole size={15} /> Privacy</button>
          <button className="nav-item" onClick={() => go('/')}><UserRound size={15} /> Switch role</button>
        </nav>
        <div className="spacer" />
        <div className="runtime-card">
          <div className={`runtime-top ${h ? '' : 'down'}`}><span className="status-dot" /> {h ? 'Running on this device' : 'Service unreachable'}</div>
          <strong>{h?.device ?? 'HP ZGX Nano'}</strong>
          <span>{h?.inference_local ? 'All AI inference local · no cloud AI' : '—'}</span>
        </div>
      </aside>

      <main className="main-shell">
        <div className="topbar">
          <span className="crumb">{area === 'physio' ? 'Physiotherapist' : area === 'patient' ? 'Patient' : 'Recovery Monitor'}</span>
          {h && (
            <span className={`net-pill ${h.network_reachable ? 'online' : 'offline'}`}>
              {h.network_reachable ? <Wifi size={13} /> : <WifiOff size={13} />}
              {h.network_reachable ? 'Online · analysis stays on this device' : 'Offline · still working'}
            </span>
          )}
        </div>
        <div className="content">{page}</div>
      </main>
    </div>
  );
}

function RolePicker() {
  const patients = useLoad(() => api.patients(), []);
  return (
    <div className="page role-picker">
      <header className="page-heading">
        <div>
          <span className="eyebrow">Recovery Monitor</span>
          <h1>Rehab exercise evidence, measured on this device</h1>
          <p className="page-subtitle">Patients record their exercises at home. The system measures every rep and flags what
            a physiotherapist should look at. The physiotherapist decides.</p>
        </div>
      </header>
      <div className="role-grid">
        <div className="role-card">
          <h2>I'm a patient</h2>
          <p>Record today's session and see how it went.</p>
          {patients.data?.map((p) => (
            <button key={p.id} className="role-person" onClick={() => go(`/patient/${p.id}`)}>
              <Initials name={p.name} /> <span>{p.name}</span>
            </button>
          ))}
          {patients.error && <p className="muted small">{patients.error.message}</p>}
        </div>
        <div className="role-card">
          <h2>I'm a physiotherapist</h2>
          <p>Review flagged sessions and set each patient's plan.</p>
          <button className="primary-button" onClick={() => go('/physio')}><ClipboardList size={15} /> Open review queue</button>
        </div>
      </div>
      <p className="muted small">Demo patients use public sample data (REHAB24-6). Not a medical device.</p>
    </div>
  );
}
