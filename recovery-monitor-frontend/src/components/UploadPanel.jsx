import { Camera, CircleStop, Upload } from 'lucide-react';
import { useEffect, useRef, useState } from 'react';
import { api, followSession } from '../api.js';
import { ErrorNote, Note } from './ui.jsx';

const STAGES = {
  queued: 'Waiting to start',
  converting: 'Preparing the video',
  pose: 'Finding your joints in each frame',
  analyze: 'Measuring each rep',
  render: 'Drawing the overlay',
  done: 'Done',
  failed: 'Failed',
};

// Record in the browser (camera) or upload a file, then follow the on-device analysis live.
export default function UploadPanel({ patientId, onDone }) {
  const [mode, setMode] = useState('idle'); // idle | camera | recording | uploading | processing
  const [progress, setProgress] = useState(null);
  const [error, setError] = useState(null);
  const [countdown, setCountdown] = useState(0);
  const fileInput = useRef(null);
  const preview = useRef(null);
  const stream = useRef(null);
  const recorder = useRef(null);
  const chunks = useRef([]);

  useEffect(() => () => stream.current?.getTracks().forEach((t) => t.stop()), []);

  async function submit(file, source) {
    setError(null);
    setMode('uploading');
    try {
      const { session_id } = await api.uploadSession(patientId, file, source);
      setMode('processing');
      setProgress({ stage: 'queued', progress: 0 });
      followSession(session_id, (s) => {
        setProgress(s);
        if (s.stage === 'done' || s.stage === 'failed') {
          setMode('idle');
          if (s.stage === 'failed') setError(new Error(s.error || 'Analysis failed.'));
          onDone?.(session_id);
        }
      });
    } catch (e) {
      setError(e);
      setMode('idle');
    }
  }

  async function openCamera() {
    setError(null);
    try {
      stream.current = await navigator.mediaDevices.getUserMedia({ video: { width: 1280, height: 720 }, audio: false });
      setMode('camera');
      requestAnimationFrame(() => {
        if (preview.current) preview.current.srcObject = stream.current;
      });
    } catch {
      setError(new Error('Could not open the camera. Check permissions, or upload a video instead.'));
    }
  }

  function startRecording() {
    let n = 3;
    setCountdown(n);
    const id = setInterval(() => {
      n -= 1;
      setCountdown(n);
      if (n === 0) {
        clearInterval(id);
        chunks.current = [];
        recorder.current = new MediaRecorder(stream.current);
        recorder.current.ondataavailable = (e) => e.data.size && chunks.current.push(e.data);
        recorder.current.onstop = () => {
          stream.current.getTracks().forEach((t) => t.stop());
          const blob = new Blob(chunks.current, { type: recorder.current.mimeType || 'video/webm' });
          submit(new File([blob], 'recording.webm', { type: blob.type }), 'camera');
        };
        recorder.current.start();
        setMode('recording');
      }
    }, 1000);
  }

  const busy = mode === 'uploading' || mode === 'processing';
  return (
    <div className="upload-panel">
      {(mode === 'camera' || mode === 'recording') && (
        <div className="camera">
          <video ref={preview} autoPlay muted playsInline />
          <div className="camera-guide">Stand side-on to the camera, whole body in frame</div>
          {countdown > 0 && <div className="countdown">{countdown}</div>}
          <div className="camera-actions">
            {mode === 'camera' && countdown === 0 && (
              <button className="primary-button" onClick={startRecording}><Camera size={15} /> Start recording</button>
            )}
            {mode === 'recording' && (
              <button className="danger-button" onClick={() => recorder.current.stop()}><CircleStop size={15} /> Stop and analyse</button>
            )}
          </div>
        </div>
      )}

      {mode === 'idle' && (
        <>
          <Note>Film from the side with your whole body in frame. Knee angles are measured accurately from the side
            (about ±5°); from other angles they are much less reliable.</Note>
          <div className="upload-actions">
            <button className="primary-button" onClick={openCamera}><Camera size={15} /> Record with camera</button>
            <button className="secondary-button" onClick={() => fileInput.current.click()}><Upload size={15} /> Upload a video</button>
            <input ref={fileInput} type="file" accept="video/*" hidden
              onChange={(e) => e.target.files[0] && submit(e.target.files[0], 'upload')} />
          </div>
        </>
      )}

      {busy && (
        <div className="progress">
          <div className="progress-top">
            <strong>{mode === 'uploading' ? 'Uploading to this device…' : STAGES[progress?.stage] ?? 'Working…'}</strong>
            <span>{Math.round((progress?.progress ?? 0) * 100)}%</span>
          </div>
          <div className="bar"><div style={{ width: `${(progress?.progress ?? 0) * 100}%` }} /></div>
          <small>Analysed on this device. The video is not sent anywhere.</small>
        </div>
      )}
      <ErrorNote error={error} />
    </div>
  );
}
