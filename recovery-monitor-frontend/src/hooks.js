import { useCallback, useEffect, useState, useSyncExternalStore } from 'react';

// Tiny hash router: '#/physio/session/abc' -> ['physio', 'session', 'abc'].
function subscribe(cb) {
  window.addEventListener('hashchange', cb);
  return () => window.removeEventListener('hashchange', cb);
}
export function useRoute() {
  const hash = useSyncExternalStore(subscribe, () => window.location.hash);
  return hash.replace(/^#\/?/, '').split('/').filter(Boolean);
}
export const go = (path) => {
  window.location.hash = path;
};

// Load data; never blanks the screen on failure (error is returned alongside the last good data).
export function useLoad(loader, deps = []) {
  const [state, setState] = useState({ data: null, error: null, loading: true });
  const load = useCallback(() => {
    let alive = true;
    setState((s) => ({ ...s, loading: true }));
    loader()
      .then((data) => alive && setState({ data, error: null, loading: false }))
      .catch((error) => alive && setState((s) => ({ ...s, error, loading: false })));
    return () => {
      alive = false;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
  useEffect(load, [load]);
  return { ...state, reload: load };
}

// Poll something small (health, queue) on an interval.
export function usePoll(loader, ms, deps = []) {
  const result = useLoad(loader, deps);
  useEffect(() => {
    const id = setInterval(result.reload, ms);
    return () => clearInterval(id);
  }, [result.reload, ms]);
  return result;
}

export const fmtDate = (iso) =>
  iso ? new Date(iso).toLocaleDateString(undefined, { month: 'short', day: 'numeric' }) : '—';
export const fmtDateTime = (iso) =>
  iso
    ? new Date(iso).toLocaleString(undefined, { month: 'short', day: 'numeric', hour: 'numeric', minute: '2-digit' })
    : '—';
export const num = (v, digits = 0, unit = '') => (v === null || v === undefined ? '—' : `${Number(v).toFixed(digits)}${unit}`);
export const pct = (v) => (v === null || v === undefined || Number.isNaN(v) ? '—' : `${Math.round(v * 100)}%`);
