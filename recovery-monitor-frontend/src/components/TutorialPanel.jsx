import { Check, Download, ExternalLink, FileText, RefreshCw, Save, Sparkles, Video } from 'lucide-react';
import { useEffect, useState } from 'react';
import { api } from '../api.js';
import { ErrorNote, Panel } from './ui.jsx';
import { useLoad } from '../hooks.js';

const splitLines = (value) => value.split('\n').map((item) => item.trim()).filter(Boolean);
const joinLines = (items = []) => items.join('\n');

export default function TutorialPanel({ session, referenceVideos = [] }) {
  const tutorials = useLoad(() => api.sessionTutorials(session.id), [session.id]);
  const [tutorial, setTutorial] = useState(null);
  const [referenceId, setReferenceId] = useState('');
  const [form, setForm] = useState(null);
  const [state, setState] = useState({ saving: false, error: null });
  const [media, setMedia] = useState(null);
  const [mediaState, setMediaState] = useState({ generating: false, error: null });
  const [voiceEnabled, setVoiceEnabled] = useState(false);

  useEffect(() => {
    const existing = tutorials.data?.[0];
    if (existing) {
      setTutorial(existing);
      setFormFrom(existing);
      setMedia(existing.media || null);
    }
  }, [tutorials.data]);

  useEffect(() => {
    if (!tutorial?.id || !['queued', 'processing'].includes(media?.status)) return undefined;
    const timer = window.setInterval(async () => {
      try {
        const updated = await api.tutorial(tutorial.id);
        setTutorial(updated);
        setMedia(updated.media || null);
        if (!['queued', 'processing'].includes(updated.media?.status)) {
          setMediaState((current) => ({ ...current, generating: false, error: updated.media?.error || null }));
        }
      } catch (error) {
        setMediaState({ generating: false, error });
      }
    }, 1500);
    return () => window.clearInterval(timer);
  }, [tutorial?.id, media?.status]);

  useEffect(() => {
    if (!referenceId && referenceVideos.length) {
      setReferenceId(String(session.protocol?.reference_video_id ?? referenceVideos[0].id));
    }
  }, [referenceId, referenceVideos, session.protocol?.reference_video_id]);

  function setFormFrom(value) {
    setForm({
      verified_findings: joinLines(value.verified_findings),
      coaching_cues: joinLines(value.coaching_cues),
      warnings: joinLines(value.warnings),
      captions: joinLines(value.captions),
      script: value.script || '',
    });
  }

  function edit(key, value) {
    setForm((current) => ({ ...current, [key]: value }));
  }

  async function generateDraft() {
    setState({ saving: true, error: null });
    try {
      const created = await api.createTutorial(session.id, Number(referenceId));
      setTutorial(created);
      setFormFrom(created);
    } catch (error) {
      setState({ saving: false, error });
      return;
    }
    setState({ saving: false, error: null });
  }

  async function generateMedia() {
    if (!tutorial || !reference?.id) return;
    setMediaState({ generating: true, error: null });
    try {
      const queued = await api.generateTutorialMedia(tutorial.id, voiceEnabled);
      setMedia((current) => ({ ...(current || {}), ...queued, status: queued.media_status }));
    } catch (error) {
      setMediaState({ generating: false, error });
    }
  }

  async function saveAnd(action) {
    setState({ saving: true, error: null });
    try {
      const payload = {
        verified_findings: splitLines(form.verified_findings),
        coaching_cues: splitLines(form.coaching_cues),
        warnings: splitLines(form.warnings),
        captions: splitLines(form.captions),
        script: form.script,
      };
      let updated = await api.updateTutorial(tutorial.id, payload);
      if (action === 'approve') updated = await api.approveTutorial(tutorial.id);
      if (action === 'changes') updated = await api.requestTutorialChanges(tutorial.id);
      setTutorial(updated);
      setFormFrom(updated);
      setMedia(updated.media || null);
      setState({ saving: false, error: null });
      tutorials.reload();
    } catch (error) {
      setState({ saving: false, error });
    }
  }

  const editing = tutorial && tutorial.status !== 'approved';
  const reference = tutorial?.reference_video;
  const referenceUrl = reference?.url || (reference?.id ? `/api/reference-videos/${reference.id}/video` : null);
  const approvedReference = Boolean(reference?.id && (!referenceVideos.length || referenceVideos.some((video) => video.id === reference.id)));
  const mediaUrl = media?.url || (tutorial?.id && media?.status === 'ready' ? `/api/tutorials/${tutorial.id}/media` : null);
  const mediaBusy = ['queued', 'processing'].includes(media?.status) || mediaState.generating;

  return (
    <Panel title={<><Sparkles size={16} /> AI exercise tutorial</>} subtitle="Text tutorial plus an approved reference video">
      {tutorials.error && <ErrorNote error={tutorials.error} />}
      {!tutorial && (
        <>
          {!session.review && <p className="muted small">Review and decide this session first, then generate a tutorial draft from its verified evidence.</p>}
          {session.review && (
            <>
              <label className="field"><span>Approved reference video</span>
                <select value={referenceId} onChange={(event) => setReferenceId(event.target.value)} disabled={!referenceVideos.length}>
                  {!referenceVideos.length && <option value="">No reference videos available</option>}
                  {referenceVideos.map((video) => <option key={video.id} value={video.id}>{video.title}</option>)}
                </select>
              </label>
              <button type="button" className="primary-button" disabled={state.saving || !referenceId} onClick={generateDraft}>
                <Sparkles size={15} /> {state.saving ? 'Generating draft…' : 'Generate tutorial draft'}
              </button>
            </>
          )}
        </>
      )}

      {tutorial && form && (
        <div className="tutorial-editor">
          <div className="tutorial-meta"><span className={`badge ${tutorial.status === 'approved' ? 'badge-green' : tutorial.status === 'request_changes' ? 'badge-amber' : 'badge-grey'}`}>{tutorial.status.replace('_', ' ')}</span><span className="muted small">{tutorial.exercise} · {tutorial.target_reps} repetitions{tutorial.target_depth_deg ? ` · ${tutorial.target_depth_deg}° depth` : ''}</span></div>
          {referenceUrl && <div className="reference"><span className="mini-label"><Video size={13} /> Approved reference video: {reference?.title}</span><video src={referenceUrl} controls playsInline preload="metadata" /></div>}
          <div className="tutorial-media">
            <div className="mini-label"><Video size={13} /> Tutorial video</div>
            {!approvedReference && <p className="muted small">Add an approved reference video before generating tutorial media.</p>}
            {approvedReference && (
              <>
                <label className="check-row"><input type="checkbox" checked={voiceEnabled} onChange={(event) => setVoiceEnabled(event.target.checked)} disabled={mediaBusy} /> Add optional local voice guidance</label>
                <button type="button" className="primary-button" disabled={mediaBusy || !approvedReference} onClick={generateMedia}>
                  <Video size={15} /> {mediaBusy ? 'Generating tutorial video…' : 'Generate tutorial video'}
                </button>
              </>
            )}
            {media?.status === 'queued' && <p className="muted small">Queued on this device…</p>}
            {media?.status === 'processing' && <div className="progress"><div className="progress-top"><span>Rendering captions and coaching cues</span><span>In progress</span></div><progress max="1" value="0.5" /></div>}
            {media?.status === 'failed' && <ErrorNote error={new Error(media.error || 'Tutorial video generation failed.')} />}
            {mediaState.error && <ErrorNote error={mediaState.error} />}
            {media?.status === 'ready' && mediaUrl && <div className="reference"><span className="mini-label"><Sparkles size={13} /> Generated tutorial preview</span><video src={mediaUrl} controls playsInline preload="metadata" /><div className="decision-actions"><a className="secondary-button" href={mediaUrl} target="_blank" rel="noreferrer"><ExternalLink size={14} /> Open video</a><a className="secondary-button" href={mediaUrl} download><Download size={14} /> Download MP4</a></div><p className="muted small">{media.voice_status === 'generated' ? 'Local voice guidance included.' : media.voice_enabled ? 'Video generated without voice guidance because no local TTS engine was available.' : 'Video generated without voice guidance.'}</p></div>}
          </div>
          <label className="field"><span>Verified movement findings</span><textarea rows={3} value={form.verified_findings} onChange={(event) => edit('verified_findings', event.target.value)} disabled={!editing} /></label>
          <label className="field"><span>Personalized coaching cues <small>(one per line)</small></span><textarea rows={3} value={form.coaching_cues} onChange={(event) => edit('coaching_cues', event.target.value)} disabled={!editing} /></label>
          <label className="field"><span>Warnings <small>(one per line)</small></span><textarea rows={3} value={form.warnings} onChange={(event) => edit('warnings', event.target.value)} disabled={!editing} /></label>
          <label className="field"><span>Captions <small>(one per line)</small></span><textarea rows={3} value={form.captions} onChange={(event) => edit('captions', event.target.value)} disabled={!editing} /></label>
          <label className="field"><span>Instruction script</span><textarea rows={4} value={form.script} onChange={(event) => edit('script', event.target.value)} disabled={!editing} /></label>
          {editing && <div className="decision-actions">
            <button type="button" className="secondary-button" disabled={state.saving} onClick={() => saveAnd('changes')}><RefreshCw size={14} /> Request changes</button>
            <button type="button" className="secondary-button" disabled={state.saving} onClick={() => saveAnd('save')}><Save size={14} /> Save edits</button>
            <button type="button" className="primary-button success" disabled={state.saving} onClick={() => saveAnd('approve')}><Check size={14} /> Approve tutorial</button>
          </div>}
          {!editing && <p className="muted small"><FileText size={13} /> This approved tutorial is now available to the patient.</p>}
          <ErrorNote error={state.error} />
        </div>
      )}
    </Panel>
  );
}
