import { CalendarCheck, MessageSquareText, PlayCircle } from 'lucide-react';
import { useState } from 'react';
import { api } from '../api.js';
import SessionPlayer from '../components/SessionPlayer.jsx';
import TrendChart from '../components/TrendChart.jsx';
import UploadPanel from '../components/UploadPanel.jsx';
import { Disclaimer, ErrorNote, Note, Panel, Stat } from '../components/ui.jsx';
import { fmtDate, fmtDateTime, num, useLoad } from '../hooks.js';

export default function PatientHome({ patientId }) {
  const patient = useLoad(() => api.patient(patientId), [patientId]);
  const history = useLoad(() => api.patientSessions(patientId), [patientId]);
  const latestId = history.data?.length ? history.data[history.data.length - 1].id : null;
  const latest = useLoad(() => (latestId ? api.session(latestId) : Promise.resolve(null)), [latestId]);
  const refs = useLoad(() => api.referenceVideos(), []);

  const protocol = patient.data?.protocol;
  const refVideo = refs.data?.find((r) => r.id === (latest.data?.review?.reference_video_id ?? protocol?.reference_video_id));
  const refresh = () => {
    history.reload();
    latest.reload();
  };

  return (
    <div className="page">
      <header className="page-heading">
        <div>
          <span className="eyebrow">Patient portal</span>
          <h1>Hi {patient.data?.name?.split(' ')[0] ?? ''}</h1>
          <p className="page-subtitle">{patient.data?.condition}</p>
        </div>
      </header>
      <ErrorNote error={patient.error || history.error} />

      <div className="grid-2">
        <Panel title="Today's exercise" subtitle={protocol ? `Plan version ${protocol.version}, set ${fmtDate(protocol.created_at)} by your physiotherapist` : ''}>
          {protocol ? (
            <>
              <div className="stats-row">
                <Stat label="Exercise" value={protocol.exercise === 'squat' ? 'Squats' : 'Leg extension'} />
                <Stat label="Repetitions" value={protocol.target_reps} />
                <Stat label="Target depth" value={`${protocol.target_depth_deg}°`} sub="knee angle at the bottom" />
              </div>
              {protocol.tempo && <p className="plan-line"><CalendarCheck size={14} /> {protocol.tempo}</p>}
              {protocol.notes && <p className="plan-line"><MessageSquareText size={14} /> {protocol.notes}</p>}
              {refVideo && (
                <div className="reference">
                  <span className="mini-label"><PlayCircle size={13} /> How it should look: {refVideo.title}</span>
                  <video src={refVideo.url} controls playsInline preload="metadata" />
                </div>
              )}
            </>
          ) : (
            <Note>Your physiotherapist hasn't set a plan yet.</Note>
          )}
        </Panel>

        <Panel title="Record today's session" subtitle="Your video is analysed on this device only">
          <UploadPanel patientId={patientId} onDone={refresh} />
        </Panel>
      </div>

      {latest.data && <LatestSession session={latest.data} patientId={patientId} refVideo={refVideo} onSaved={refresh} />}

      <Panel title="Your progress" subtitle="From your analysed sessions">
        <TrendChart sessions={history.data} targetDepth={protocol?.target_depth_deg} />
      </Panel>
      <Disclaimer />
    </div>
  );
}

function LatestSession({ session, patientId, refVideo, onSaved }) {
  const r = session.result;
  const review = session.review;
  const target = r?.protocol?.target_reps ?? session.protocol?.target_reps;
  const flagged = r?.reps?.filter((x) => !x.predicted_correct).length ?? 0;

  if (session.stage !== 'done') {
    return (
      <Panel title={`Session from ${fmtDateTime(session.created_at)}`}>
        {session.stage === 'failed' ? <Note tone="error">{session.error}</Note> : <Note>Still being analysed…</Note>}
      </Panel>
    );
  }

  return (
    <Panel title={`Your last session · ${fmtDateTime(session.created_at)}`}
      subtitle={review ? 'Reviewed by your physiotherapist' : flagged ? 'Sent to your physiotherapist for review' : 'Analysed on this device'}>
      {r.status === 'rejected_quality' && (
        <Note tone="warn">
          <strong>We couldn't measure this video reliably.</strong>
          <ul>{r.quality.instructions.map((m) => <li key={m}>{m}</li>)}</ul>
        </Note>
      )}
      {r.status !== 'rejected_quality' && (
        <>
          <div className="stats-row">
            <Stat label="Reps done" value={`${r.repetitions}${target ? ` / ${target}` : ''}`} />
            <Stat label="Reached target depth" value={`${r.metrics?.reps_reaching_target ?? 0} of ${r.repetitions}`} />
            <Stat label="Deepest squat" value={num(r.metrics?.min_knee_angle_deg, 0, '°')} />
            <Stat label="For your physio to check" value={flagged} tone={flagged ? 'amber' : 'green'}
              sub={flagged ? 'reps looked different from your approved form' : 'nothing flagged'} />
          </div>
          {r.quality?.instructions?.length > 0 && <Note tone="warn">{r.quality.instructions.join(' ')}</Note>}
        </>
      )}

      {review && (
        <div className={`feedback ${review.decision}`}>
          <strong>{review.decision === 'approve' ? 'Your physiotherapist approved this session' : 'Your physiotherapist asked for changes'}</strong>
          {review.notes && <p>“{review.notes}”</p>}
          <small>{fmtDateTime(review.created_at)}</small>
        </div>
      )}

      <div className={refVideo && review ? 'side-by-side' : ''}>
        <div>
          {refVideo && review && <span className="mini-label">You</span>}
          <SessionPlayer session={session} />
        </div>
        {refVideo && review && (
          <div>
            <span className="mini-label">How it should look</span>
            <div className="video-frame"><video src={refVideo.url} controls playsInline preload="metadata" /></div>
          </div>
        )}
      </div>

      {!session.check_in ? <CheckIn patientId={patientId} sessionId={session.id} onSaved={onSaved} /> : (
        <p className="muted small">You reported pain {session.check_in.pain_score}/10 for this session.</p>
      )}
    </Panel>
  );
}

function CheckIn({ patientId, sessionId, onSaved }) {
  const [pain, setPain] = useState(null);
  const [stiff, setStiff] = useState(false);
  const [comment, setComment] = useState('');
  const [state, setState] = useState({ saving: false, error: null });

  async function save() {
    setState({ saving: true, error: null });
    try {
      await api.checkIn(patientId, sessionId, { pain_score: pain, stiffness: stiff, comment });
      onSaved();
    } catch (error) {
      setState({ saving: false, error });
    }
  }

  return (
    <div className="checkin">
      <h3>How did it feel?</h3>
      <div className="pain-scale" role="radiogroup" aria-label="Pain from 0 to 10">
        {Array.from({ length: 11 }, (_, i) => (
          <button key={i} className={pain === i ? 'selected' : ''} onClick={() => setPain(i)} aria-pressed={pain === i}>{i}</button>
        ))}
      </div>
      <div className="pain-labels"><span>No pain</span><span>Worst pain</span></div>
      <label className="check"><input type="checkbox" checked={stiff} onChange={(e) => setStiff(e.target.checked)} /> My knee felt stiff</label>
      <textarea placeholder="Anything your physiotherapist should know? (optional)" value={comment}
        onChange={(e) => setComment(e.target.value)} rows={2} />
      <button className="primary-button" disabled={pain === null || state.saving} onClick={save}>
        {state.saving ? 'Saving…' : 'Send to my physiotherapist'}
      </button>
      <ErrorNote error={state.error} />
    </div>
  );
}
