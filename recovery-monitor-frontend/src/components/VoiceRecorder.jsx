import { Mic, Square } from 'lucide-react';
import { useRef, useState } from 'react';
import { api } from '../api.js';
import { ErrorNote } from './ui.jsx';

// Record a short voice note; Whisper on this device turns it into text the patient can check and edit.
export default function VoiceRecorder({ patientId, sessionId, onTranscript }) {
  const [state, setState] = useState('idle'); // idle | recording | transcribing
  const [seconds, setSeconds] = useState(0);
  const [error, setError] = useState(null);
  const rec = useRef(null);
  const timer = useRef(null);

  async function start() {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const chunks = [];
      const r = new MediaRecorder(stream);
      r.ondataavailable = (e) => e.data.size && chunks.push(e.data);
      r.onstop = async () => {
        stream.getTracks().forEach((t) => t.stop());
        clearInterval(timer.current);
        setState('transcribing');
        try {
          const blob = new Blob(chunks, { type: r.mimeType || 'audio/webm' });
          const res = await api.voiceNote(patientId, sessionId, new File([blob], 'voice.webm', { type: blob.type }));
          onTranscript(res.text);
        } catch (e) {
          setError(e);
        }
        setState('idle');
      };
      r.start();
      rec.current = r;
      setSeconds(0);
      timer.current = setInterval(() => setSeconds((s) => {
        if (s >= 59) r.stop(); // keep notes short
        return s + 1;
      }), 1000);
      setState('recording');
    } catch {
      setError(new Error('Could not open the microphone. Check permissions, or type your answer instead.'));
    }
  }

  return (
    <div className="voice">
      {state === 'idle' && (
        <button className="secondary-button" onClick={start}><Mic size={15} /> Tell us how it felt (voice)</button>
      )}
      {state === 'recording' && (
        <button className="danger-button" onClick={() => rec.current.stop()}>
          <Square size={13} /> Stop · 0:{String(seconds).padStart(2, '0')}
        </button>
      )}
      {state === 'transcribing' && <span className="muted small">Turning your voice into text on this device…</span>}
      <ErrorNote error={error} />
    </div>
  );
}
