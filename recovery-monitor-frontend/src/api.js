// All backend calls in one place. URLs are relative (/api/...): Vite proxies them in development and the
// backend serves this app in the demo build.

async function request(path, options = {}) {
  let res;
  try {
    res = await fetch(path, options);
  } catch {
    throw new Error('The Recovery Monitor service on this device is not reachable.');
  }
  if (!res.ok) {
    let detail = `${res.status} ${res.statusText}`;
    try {
      const body = await res.json();
      detail = typeof body.detail === 'string' ? body.detail : JSON.stringify(body.detail);
    } catch {
      /* keep status text */
    }
    const err = new Error(detail);
    err.status = res.status;
    throw err;
  }
  return res.status === 204 ? null : res.json();
}

const json = (method, body) => ({
  method,
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify(body),
});

export const api = {
  health: () => request('/api/health'),
  evalSummary: () => request('/api/eval/summary'),

  patients: () => request('/api/patients'),
  patient: (id) => request(`/api/patients/${id}`),
  patientSessions: (id) => request(`/api/patients/${id}/sessions`),
  setProtocol: (id, protocol) => request(`/api/patients/${id}/protocol`, json('POST', protocol)),

  session: (id) => request(`/api/sessions/${id}`),
  uploadSession: (patientId, file, source = 'upload') => {
    const body = new FormData();
    body.append('video', file, file.name || 'recording.webm');
    body.append('source', source);
    return request(`/api/patients/${patientId}/sessions`, { method: 'POST', body });
  },
  checkIn: (patientId, sessionId, data) =>
    request(`/api/patients/${patientId}/sessions/${sessionId}/check-in`, json('POST', data)),
  deleteSession: (id) => request(`/api/sessions/${id}`, { method: 'DELETE' }),

  reviewQueue: () => request('/api/review-queue'),
  review: (sessionId, data) => request(`/api/sessions/${sessionId}/review`, json('POST', data)),
  referenceVideos: () => request('/api/reference-videos?exercise=squat'),
};

// Live analysis progress over Server-Sent Events. Returns a function that stops listening.
export function followSession(sessionId, onUpdate) {
  const es = new EventSource(`/api/sessions/${sessionId}/events`);
  const handle = (e) => onUpdate(JSON.parse(e.data));
  es.addEventListener('progress', handle);
  es.addEventListener('done', (e) => {
    handle(e);
    es.close();
  });
  es.addEventListener('failed', (e) => {
    handle(e);
    es.close();
  });
  es.onerror = () => es.close();
  return () => es.close();
}
