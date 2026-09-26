import { BookOpenText, Download, ExternalLink, Video } from 'lucide-react';
import { api } from '../api.js';
import { ErrorNote, Note, Panel } from './ui.jsx';
import { useLoad } from '../hooks.js';

export default function PatientTutorials() {
  const tutorials = useLoad(() => api.patientTutorials(), []);

  return (
    <Panel title={<><BookOpenText size={16} /> Your exercise tutorials</>} subtitle="Tutorials approved by your physiotherapist">
      <ErrorNote error={tutorials.error} />
      {!tutorials.data?.length && !tutorials.error && <Note>Your approved tutorials will appear here after your physiotherapist reviews them.</Note>}
      <div className="tutorial-list">
        {tutorials.data?.map((tutorial) => {
          const mediaUrl = tutorial.media?.status === 'ready'
            ? (tutorial.media.url || `/api/tutorials/${tutorial.id}/media`)
            : null;
          return <article className="tutorial-card" key={tutorial.id}>
            <div className="tutorial-meta"><span className="badge badge-green">Approved</span><strong>{tutorial.exercise}</strong><span>{tutorial.target_reps} repetitions{tutorial.target_depth_deg ? ` · ${tutorial.target_depth_deg}° depth` : ''}</span></div>
            {mediaUrl ? <div className="reference"><span className="mini-label"><Video size={13} /> Your approved tutorial video</span><video src={mediaUrl} controls playsInline preload="metadata" /><div className="decision-actions"><a className="secondary-button" href={mediaUrl} target="_blank" rel="noreferrer"><ExternalLink size={14} /> Open video</a><a className="secondary-button" href={mediaUrl} download><Download size={14} /> Download MP4</a></div></div> : <Note>Your therapist approved this tutorial, but the rendered video is not available yet. You can still follow the instructions below.</Note>}
            <section><h3>Instructions and personalized coaching</h3><p>{tutorial.script}</p></section>
            <section><h3>Coaching cues</h3><ul>{tutorial.coaching_cues.map((cue) => <li key={cue}>{cue}</li>)}</ul></section>
            {tutorial.warnings.length > 0 && <section className="tutorial-warnings"><h3>Warnings</h3><ul>{tutorial.warnings.map((warning) => <li key={warning}>{warning}</li>)}</ul></section>}
            <section><h3>Captions</h3><ul>{tutorial.captions.map((caption) => <li key={caption}>{caption}</li>)}</ul></section>
          </article>;
        })}
      </div>
    </Panel>
  );
}
