import { ChevronDown, ChevronRight, Cpu, LogOut, ShieldCheck, UserRound, WifiOff } from 'lucide-react';
import { useEffect, useLayoutEffect, useRef, useState } from 'react';
import { api } from '../api.js';
import { go } from '../hooks.js';

// Heartbeat line that draws itself: the app is "alive" and watching movement.
export function BrandMark() {
  return (
    <span className="brand-mark" aria-hidden="true">
      <svg viewBox="0 0 24 24"><path className="ecg" d="M2 12h4l2-5 4 10 3-7 2 2h5" /></svg>
    </span>
  );
}

// Nav group with one highlight pill that glides to the active item (interruptible CSS transition).
export function NavGroup({ items }) {
  const list = useRef(null);
  const [pill, setPill] = useState(null);
  const active = items.findIndex((i) => i.active);
  useLayoutEffect(() => {
    const el = active >= 0 ? list.current?.children[active + 1] : null;
    setPill(el ? { top: el.offsetTop, height: el.offsetHeight } : null);
  }, [active, items.length]);
  return (
    <nav className="nav-list" ref={list}>
      <span className={`nav-pill ${pill ? 'on' : ''}`} style={pill ? { transform: `translateY(${pill.top}px)`, height: pill.height } : undefined} />
      {items.map(({ path, label, Icon, tint, active: on, count, onClick }) => (
        <button key={label} className={`nav-item ${on ? 'active' : ''}`} aria-current={on ? 'page' : undefined}
          onClick={onClick ?? (() => go(path))}>
          <span className={`nav-icon ${tint}`}><Icon size={14} strokeWidth={2.2} /></span>
          <span className="nav-text">{label}</span>
          {count ? <span className="nav-count">{count}</span> : null}
        </button>
      ))}
    </nav>
  );
}

// Live status of every model in the pipeline, straight from /api/health.
export function DeviceCard({ health }) {
  const ai = health?.ai ?? {};
  const vs = ai.vision_and_speech?.ok;
  const models = [
    ['Body tracking', 'MediaPipe pose', Boolean(health)],
    ['Form check', 'XGBoost × 6', Boolean(health)],
    ['Vision model', 'Qwen3-VL fine-tuned', vs],
    ['Voice notes', 'Whisper turbo', vs],
    ['Report writer', ai.llm?.model ?? 'local LLM', ai.llm?.ok],
  ];
  const up = models.filter((m) => m[2]).length;
  return (
    <div className={`device-card ${health ? '' : 'down'}`}>
      <div className="device-top">
        <span className="device-chip"><Cpu size={15} /></span>
        <div>
          <strong>{health?.device?.replace(/ \(.*\)/, '') ?? 'HP ZGX Nano'}</strong>
          <small>{health ? `NVIDIA GB10 · ${up}/${models.length} models live` : 'Service unreachable'}</small>
        </div>
        <span className="eq" aria-hidden="true"><i /><i /><i /><i /></span>
      </div>
      <ul className="model-list">
        {models.map(([name, detail, ok], i) => (
          <li key={name} style={{ '--i': i }} className={ok ? 'ok' : 'off'} title={detail}>
            <span className="led" /><span>{name}</span><small>{detail}</small>
          </li>
        ))}
      </ul>
      <div className="device-foot"><ShieldCheck size={12} /> {health?.cloud_ai_disabled ? 'Cloud AI off · nothing leaves the device' : 'Checking…'}</div>
    </div>
  );
}

// Toolbar: where you are, a privacy signal, and the account menu.
export function Topbar({ crumbs, health, user }) {
  return (
    <div className="topbar">
      <nav className="crumbs" aria-label="Breadcrumb">
        {crumbs.map(([label, path], i) => (
          <span key={label} className="crumb-part">
            {i > 0 && <ChevronRight size={14} className="crumb-sep" />}
            {path && i < crumbs.length - 1
              ? <button className="crumb-link" onClick={() => go(path)}>{label}</button>
              : <span className={i === crumbs.length - 1 ? 'crumb-current' : ''}>{label}</span>}
          </span>
        ))}
      </nav>
      {health && (
        <span className={`privacy-pill ${health.network_reachable ? '' : 'offline'}`}>
          {health.network_reachable ? <ShieldCheck size={14} /> : <WifiOff size={14} />}
          <span>{health.network_reachable ? 'Private · all AI runs on this device' : 'Offline · still working'}</span>
        </span>
      )}
      <AccountMenu user={user} />
    </div>
  );
}

function AccountMenu({ user }) {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const root = useRef(null);
  useEffect(() => {
    if (!open) return undefined;
    const close = (e) => { if (e.type === 'keydown' ? e.key === 'Escape' : !root.current?.contains(e.target)) setOpen(false); };
    document.addEventListener('pointerdown', close);
    document.addEventListener('keydown', close);
    return () => { document.removeEventListener('pointerdown', close); document.removeEventListener('keydown', close); };
  }, [open]);
  if (!user) return <span />;
  const therapist = user.role === 'therapist';
  const profilePath = therapist ? '/onboarding/therapist' : '/onboarding/patient';
  const name = user.name || user.email.split('@')[0].replace(/[._]/g, ' ');
  const initials = name.split(' ').map((w) => w[0]).join('').slice(0, 2).toUpperCase();
  const logout = async () => { setBusy(true); try { await api.authLogout(); } finally { go('/signin'); } };
  const pick = (fn) => () => { setOpen(false); fn(); };
  return (
    <div className={`account ${open ? 'open' : ''}`} ref={root}>
      <button className="account-trigger" aria-haspopup="menu" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
        <span className={`account-avatar ${therapist ? 'therapist' : 'patient'}`}>{initials}</span>
        <span className="account-name"><strong>{name}</strong><small>{therapist ? 'Physiotherapist' : 'Patient'}</small></span>
        <ChevronDown size={14} className="account-chevron" />
      </button>
      <div className="account-menu" role="menu" inert={!open}>
        <div className="account-head">
          <span className={`account-avatar big ${therapist ? 'therapist' : 'patient'}`}>{initials}</span>
          <div><strong>{name}</strong><small>{user.email}</small></div>
        </div>
        <button role="menuitem" onClick={pick(() => go(profilePath))}><UserRound size={15} /> Edit profile</button>
        <button role="menuitem" onClick={pick(() => go('/privacy'))}><ShieldCheck size={15} /> Privacy & data</button>
        <div className="menu-sep" />
        <button role="menuitem" className="danger" disabled={busy} onClick={pick(logout)}><LogOut size={15} /> Log out</button>
      </div>
    </div>
  );
}
