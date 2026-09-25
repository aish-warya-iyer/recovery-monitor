import { AlertTriangle, ChevronDown, CircleCheck, Info } from 'lucide-react';
import { useId, useState } from 'react';

export function Panel({ title, subtitle, action, children, className = '' }) {
  return (
    <section className={`panel ${className}`}>
      {(title || action) && (
        <div className="panel-heading">
          <div>
            {title && <h2>{title}</h2>}
            {subtitle && <span>{subtitle}</span>}
          </div>
          {action}
        </div>
      )}
      {children}
    </section>
  );
}

const SEVERITY = {
  urgent: ['badge-red', 'Urgent review'],
  review: ['badge-amber', 'Needs review'],
  none: ['badge-green', 'No flags'],
};
export function FlagBadge({ flag }) {
  if (!flag) return <span className="badge badge-grey">Analysing</span>;
  const [cls, label] = SEVERITY[flag.severity] ?? SEVERITY.none;
  return <span className={`badge ${cls}`}>{label}</span>;
}

export function RepVerdict({ rep }) {
  return rep.predicted_correct ? (
    <span className="badge badge-green">Looks good</span>
  ) : (
    <span className="badge badge-amber">Review</span>
  );
}

export function Stat({ label, value, sub, tone = '' }) {
  return (
    <div className={`stat ${tone}`}>
      <span className="stat-label">{label}</span>
      <strong>{value}</strong>
      {sub && <small>{sub}</small>}
    </div>
  );
}

export function Note({ tone = 'info', children }) {
  const Icon = tone === 'error' || tone === 'warn' ? AlertTriangle : tone === 'ok' ? CircleCheck : Info;
  return (
    <div className={`note note-${tone}`}>
      <Icon size={15} />
      <div>{children}</div>
    </div>
  );
}

export function ErrorNote({ error }) {
  return error ? <Note tone="error">{error.message ?? String(error)}</Note> : null;
}

export function Disclaimer() {
  return (
    <p className="disclaimer">
      Movement measurements to support your physiotherapist. Not a diagnosis or medical advice.
    </p>
  );
}

export function Initials({ name, className = '' }) {
  const s = (name || '?').split(' ').map((w) => w[0]).join('').slice(0, 2).toUpperCase();
  return <span className={`initials ${className}`}>{s}</span>;
}

// Progressive disclosure: a summary stays visible, details open on request (animated, reduced-motion safe).
export function Disclosure({ label, openLabel, children, defaultOpen = false, className = '' }) {
  const [open, setOpen] = useState(defaultOpen);
  const id = useId();
  return (
    <div className={`disclosure ${open ? 'open' : ''} ${className}`}>
      <button type="button" className="disclosure-toggle" aria-expanded={open} aria-controls={id} onClick={() => setOpen((o) => !o)}>
        <span>{open ? (openLabel ?? label) : label}</span>
        <ChevronDown size={15} className="disclosure-chevron" />
      </button>
      <div id={id} className="disclosure-body" inert={!open}>
        <div className="disclosure-inner">{children}</div>
      </div>
    </div>
  );
}
