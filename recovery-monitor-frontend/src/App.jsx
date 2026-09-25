import * as React from 'react';
import { Activity, ArrowRight, BarChart3, Check, ClipboardList, HeartPulse, LockKeyhole, ShieldCheck, Sparkles, UserRound, Wifi, WifiOff } from 'lucide-react';
import { api } from './api.js';
import rehabMotionPerson from './assets/rehab-motion-person.png';
import rehabMotionPersonStanding from './assets/rehab-motion-person-standing.png';
import exerciseLibraryStrip from './assets/exercise-library-strip.png';
import { go, useLoad, usePoll, useRoute } from './hooks.js';
import Evaluation from './pages/Evaluation.jsx';
import PatientHome from './pages/PatientHome.jsx';
import PhysioPatient from './pages/PhysioPatient.jsx';
import PhysioQueue from './pages/PhysioQueue.jsx';
import PhysioSession from './pages/PhysioSession.jsx';
import Privacy from './pages/Privacy.jsx';
import SignIn from './pages/SignIn.jsx';
import SignUp from './pages/SignUp.jsx';
import RoleSelect from './pages/RoleSelect.jsx';
import PatientOnboarding from './pages/PatientOnboarding.jsx';
import PatientIntake from './pages/PatientIntake.jsx';
import TherapistOnboarding from './pages/TherapistOnboarding.jsx';

export default function App() {
  const route = useRoute();
  const [area, a, b] = route;
  const isLanding = !area;
  const isAuthPage = ['signin', 'signup', 'role', 'onboarding'].includes(area);
  const health = usePoll(() => api.health(), 5000);
  const queue = usePoll(() => (area === 'physio' ? api.reviewQueue() : Promise.resolve(null)), 10000, [area]);
  const me = useLoad(() => api.authMe(), [area]);

  let page;
  if (area === 'signin') page = <SignIn />;
  else if (area === 'signup') page = <SignUp />;
  else if (area === 'role') page = <RoleSelect />;
  else if (area === 'onboarding' && a === 'patient') page = <PatientOnboarding />;
  else if (area === 'onboarding' && a === 'therapist') page = <TherapistOnboarding />;
  else if (area === 'patient' && a === 'intake') page = <PatientIntake />;
  else if (area === 'patient' && (a || me.data?.user?.role === 'patient')) page = <PatientHome key={a ?? me.data.user.id} patientId={a ?? me.data.user.id} />;
  else if (area === 'physio' && a === 'session' && b) page = <PhysioSession key={b} sessionId={b} />;
  else if (area === 'physio' && a === 'patient' && b) page = <PhysioPatient key={b} patientId={b} />;
  else if (area === 'physio') page = <PhysioQueue />;
  else if (area === 'evaluation') page = <Evaluation />;
  else if (area === 'privacy') page = <Privacy />;
  else page = <RolePicker user={me.data?.user} />;

  const patientRouteId = a ?? me.data?.user?.id;
  const nav = area === 'patient'
    ? [[`/patient/${patientRouteId}`, 'My sessions', HeartPulse, true]]
    : area === 'physio'
      ? [['/physio', 'Review queue', ClipboardList, !a, queue.data?.length]]
      : [];
  const h = health.data;

  if (isAuthPage) return <div className="auth-shell">{page}</div>;

  return (
    <div className={`app-shell ${isLanding ? 'landing-shell' : ''}`}>
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
          <AccountActions user={me.data?.user} />
        </div>
        <div className="content">{page}</div>
      </main>
    </div>
  );
}

function RolePicker({ user }) {
  const patients = useLoad(() => api.patients(), []);
  const demoPatient = patients.data?.[0];
  const scrollToStory = () => document.getElementById('story')?.scrollIntoView({ behavior: 'smooth' });

  return (
    <div className="landing-page">
      <header className="landing-nav">
        <button className="landing-brand" onClick={() => go('/')} aria-label="Recovery Monitor home">
          <span className="brand-mark"><Activity size={18} /></span>
          <span><strong>Recovery Monitor</strong><small>On-device rehab evidence</small></span>
        </button>
        <nav className="landing-links" aria-label="About Recovery Monitor">
          <button onClick={scrollToStory}>How it works</button>
          <button onClick={() => go('/evaluation')}>Accuracy</button>
          <button onClick={() => go('/privacy')}>Privacy</button>
        </nav>
        <button className="nav-login" onClick={() => go(user ? (user.role === 'therapist' ? '/physio' : `/patient/${user.id}`) : '/signin')}>{user ? 'Open dashboard' : 'Sign in'} <ArrowRight size={15} /></button>
      </header>

      <main>
        <section className="landing-hero">
          <div className="hero-copy">
            <span className="eyebrow"><Sparkles size={13} /> Rehabilitation, made visible</span>
            <h1>The evidence layer <em>between appointments.</em></h1>
            <p className="hero-subtitle">Recovery Monitor turns everyday exercise into structured movement evidence—helping care teams see what is happening between visits, while keeping patients engaged in the work of recovery.</p>
            <div className="hero-actions">
              <button className="primary-button hero-button" onClick={() => go('/signin')}>Explore the patient experience <ArrowRight size={16} /></button>
              <button className="secondary-button hero-button" onClick={() => go('/signin')}>See the care-team workflow</button>
            </div>
            <p className="landing-note"><ShieldCheck size={15} /> Private by design. Analysis runs on this device.</p>
          </div>
          <div className="hero-orbit" aria-hidden="true">
            <div className="orbit-glow" />
            <div className="orbit-card orbit-card-main">
              <div className="orbit-card-top"><span className="mini-status"><span /> Live movement sample</span><span>Today</span></div>
              <div className="motion-figure-image"><img className="figure-standing" src={rehabMotionPersonStanding} alt="3D rehabilitation motion figure standing" /><img className="figure-squat" src={rehabMotionPerson} alt="3D rehabilitation motion figure in a squat" /></div>
              <div className="orbit-metric"><strong>04</strong><span>of 10 reps measured</span></div>
              <div className="orbit-bars"><i /><i /><i /><i /><i /><i /><i /><i /><i /><i /></div>
            </div>
            <div className="floating-chip chip-confidence"><Check size={14} /> Clear movement</div>
            <div className="floating-chip chip-local"><span className="pulse-dot" /> Local analysis</div>
          </div>
        </section>

        <section className="landing-exercises">
          <div className="section-intro"><span className="eyebrow">Dataset-backed movement library</span><h2>One platform. More ways to move.</h2><p>The research set spans six movement patterns. Squat is our current full product workflow; this library shows the path toward broader rehabilitation coverage.</p></div>
          <div className="exercise-strip-frame"><img src={exerciseLibraryStrip} alt="Six 3D rehabilitation exercise poses: arm abduction, arm V/W, push-up, leg abduction, lunge, and squat" /></div>
          <div className="exercise-labels" aria-label="Exercise coverage">
            <div><span>01</span><strong>Arm abduction</strong><small>Research coverage</small></div>
            <div><span>02</span><strong>Arm V/W</strong><small>Research coverage</small></div>
            <div><span>03</span><strong>Push-up</strong><small>Research coverage</small></div>
            <div><span>04</span><strong>Leg abduction</strong><small>Research coverage</small></div>
            <div><span>05</span><strong>Leg lunge</strong><small>Research coverage</small></div>
            <div className="exercise-live"><span>06</span><strong>Squat</strong><small>Current full workflow</small></div>
          </div>
        </section>

        <section className="landing-story" id="story">
          <div className="section-intro"><span className="eyebrow">The product loop</span><h2>Less guesswork. More useful signal.</h2><p>Recovery Monitor gives each side of the care relationship a clearer next step—without asking the patient to become a data scientist.</p></div>
          <div className="story-grid">
            <article><span className="story-number">01</span><h3>Capture the moment</h3><p>A short exercise video becomes a repeatable record of what happened at home.</p></article>
            <article><span className="story-number">02</span><h3>Translate movement</h3><p>Depth, timing, tracking quality, and change are organized into evidence people can understand.</p></article>
            <article><span className="story-number">03</span><h3>Extend the visit</h3><p>Therapists spend less time guessing what happened between appointments and more time deciding what to do next.</p></article>
          </div>
        </section>

        <section className="landing-proof">
          <div className="section-intro"><span className="eyebrow">Why this can matter at scale</span><h2>A clearer operating layer for recovery at home.</h2><p>Built around the moments that are usually invisible: the exercise, the signal, and the decision that follows.</p></div>
          <div className="proof-grid">
            <article className="proof-card proof-card-featured"><span className="proof-kicker">For care teams</span><h3>Make remote progress reviewable.</h3><p>Bring structured movement evidence into the space between appointments, with flags that invite a professional review rather than replace one.</p><button className="proof-link" onClick={() => go('/signin')}>Open the review workflow <ArrowRight size={15} /></button></article>
            <article className="proof-card"><span className="proof-kicker">For patients</span><h3>Make effort feel visible.</h3><p>Patients get a calmer feedback loop: record, understand the result, report how they feel, and keep going.</p></article>
            <article className="proof-card"><span className="proof-kicker">For organizations</span><h3>Privacy is part of the product.</h3><p>On-device inference keeps sensitive movement data close to the people and systems responsible for care.</p></article>
          </div>
        </section>

        <section className="landing-roles">
          <div className="section-intro"><span className="eyebrow">Two perspectives, one recovery</span><h2>Choose your space.</h2></div>
          <div className="role-grid">
            <div className="role-card landing-role-card patient-role">
              <div className="role-icon"><HeartPulse size={19} /></div><h2>For patients</h2><p>A gentle place to record today’s movement, understand the result, and share how your body feels.</p>
              <button className="text-button" onClick={() => go('/signin')}>Patient login <ArrowRight size={15} /></button>
              {patients.error && <span className="muted small">Demo access is temporarily unavailable.</span>}
            </div>
            <div className="role-card landing-role-card physio-role">
              <div className="role-icon"><ClipboardList size={19} /></div><h2>For physiotherapists</h2><p>A focused review queue for the sessions that deserve a closer look, with the final decision always yours.</p>
              <button className="text-button" onClick={() => go('/signin')}>Physiotherapist login <ArrowRight size={15} /></button>
            </div>
          </div>
        </section>

        <section className="landing-trust">
          <div><ShieldCheck size={23} /><strong>Your movement stays yours.</strong><p>Local inference, transparent measurements, and a clear therapist approval step.</p></div>
          <button className="secondary-button" onClick={() => go('/privacy')}>Explore privacy <ArrowRight size={15} /></button>
        </section>
      </main>
      <footer className="landing-footer"><span>Recovery Monitor</span><span>Demo experience · Not a medical device</span><span>Public sample data: REHAB24-6</span></footer>
    </div>
  );
}

function AccountActions({ user }) {
  const [busy, setBusy] = React.useState(false);
  if (!user) return null;
  const profilePath = user.role === 'therapist' ? '/onboarding/therapist' : '/onboarding/patient';
  const logout = async () => { setBusy(true); try { await api.authLogout(); } finally { go('/signin'); } };
  return <div className="account-actions"><button className="account-profile" onClick={() => go(profilePath)}><UserRound size={15} /><span><strong>{user.email}</strong><small>{user.role === 'therapist' ? 'Therapist account' : 'Patient account'}</small></span></button><button className="account-button" onClick={() => go(profilePath)}>Edit profile</button><button className="account-button danger-text" disabled={busy} onClick={logout}>Log out</button></div>;
}
