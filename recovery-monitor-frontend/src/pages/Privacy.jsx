import { Cpu, Database, HardDrive, ShieldCheck, Wifi, WifiOff } from 'lucide-react';
import { api } from '../api.js';
import { ErrorNote, Note, Panel } from '../components/ui.jsx';
import { usePoll } from '../hooks.js';

export default function Privacy() {
  const h = usePoll(() => api.health(), 4000);
  const d = h.data;
  const rows = [
    [Cpu, 'Pose estimation', 'MediaPipe Pose Landmarker, on this device’s CPU'],
    [Cpu, 'Rep analysis and form models', 'Rules + one XGBoost model per exercise, on this device'],
    [Cpu, 'Video model (fine-tuned)', 'Qwen3-VL-4B + our LoRA, on this device’s GPU: which exercise, camera view, form'],
    [Cpu, 'Voice notes', 'Whisper large-v3-turbo on this device’s GPU; the transcript is shown to the patient first'],
    [Cpu, 'Draft report for the physiotherapist', 'Local language model on this device; red flags by fixed rules; numbers checked'],
    [HardDrive, 'Videos', 'Stored on this device only; the patient or physio can delete a session and everything derived from it'],
    [Database, 'Results, check-ins, reviews', 'Local SQLite database on this device'],
    [ShieldCheck, 'Cloud AI', 'None. The service refuses to start if an AI endpoint is configured outside this device.'],
  ];

  return (
    <div className="page">
      <header className="page-heading">
        <div>
          <span className="eyebrow">Privacy</span>
          <h1>What stays on this device</h1>
          <p className="page-subtitle">Everything. Here is what runs where.</p>
        </div>
      </header>
      <ErrorNote error={h.error} />

      <Panel>
        <div className="status-grid">
          <div className="status-tile ok"><Cpu size={18} /><div><strong>{d?.device ?? '—'}</strong><span>All AI inference runs here</span></div></div>
          <div className={`status-tile ${d?.inference_local ? 'ok' : 'bad'}`}><ShieldCheck size={18} /><div><strong>{d ? (d.inference_local ? 'Local only' : 'Not local!') : '—'}</strong><span>Checked at startup and on every health check</span></div></div>
          <div className={`status-tile ${d?.network_reachable ? 'neutral' : 'ok'}`}>
            {d?.network_reachable ? <Wifi size={18} /> : <WifiOff size={18} />}
            <div><strong>{d ? (d.network_reachable ? 'Internet connected' : 'Offline') : '—'}</strong><span>Analysis works either way</span></div>
          </div>
        </div>
      </Panel>

      <Panel title="Where each piece runs">
        <table className="table">
          <tbody>{rows.map(([Icon, what, where]) => <tr key={what}><td><Icon size={15} /></td><td><strong>{what}</strong></td><td>{where}</td></tr>)}</tbody>
        </table>
      </Panel>
      <Note>Demo data is public sample data (REHAB24-6, CC BY-NC 4.0). This prototype is not a medical device and is not
        for clinical use. A production version would add authentication and healthcare-grade access controls.</Note>
    </div>
  );
}
