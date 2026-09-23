import {
  StrictMode,
  useEffect,
  useMemo,
  useRef,
  useState,
} from 'react';

import { createRoot } from 'react-dom/client';

import {
  Activity,
  ArrowUpRight,
  Bell,
  Check,
  ChevronRight,
  CircleHelp,
  ClipboardCheck,
  Clock3,
  FileText,
  HeartPulse,
  LayoutDashboard,
  LockKeyhole,
  Menu,
  MessageSquareText,
  MoreHorizontal,
  Play,
  RotateCcw,
  Settings2,
  ShieldCheck,
  Sparkles,
  Upload,
  UsersRound,
  Video,
  WifiOff,
  X,
} from 'lucide-react';

import './styles.css';


const workflow = [
  {
    label: 'Session setup',
    icon: ClipboardCheck,
  },
  {
    label: 'Movement analysis',
    icon: Activity,
  },
  {
    label: 'Patient check-in',
    icon: MessageSquareText,
  },
  {
    label: 'Therapist review',
    icon: ShieldCheck,
  },
];


function App() {
  const [activeNav, setActiveNav] = useState('Overview');

  const [analysisState, setAnalysisState] =
    useState('ready');

  const [analysisResult, setAnalysisResult] =
    useState(null);

  const [analysisError, setAnalysisError] =
    useState('');

  const [pain, setPain] = useState(3);

  const [patientComment, setPatientComment] =
    useState(
      'My knee feels a little stiff today, but better than last week.'
    );

  const [checkinState, setCheckinState] =
    useState('idle');

  const [checkinError, setCheckinError] =
    useState('');

  const [approved, setApproved] =
    useState(false);

  const [decisionState, setDecisionState] =
    useState('idle');

  const [menuOpen, setMenuOpen] =
    useState(false);

  const [selectedVideo, setSelectedVideo] =
    useState(null);

  const [videoPreviewUrl, setVideoPreviewUrl] =
    useState('');

  const videoInputRef = useRef(null);

  const sessionId = 'demo-session-001';
  const targetRepetitions = 10;


  useEffect(() => {
    if (!selectedVideo) {
      setVideoPreviewUrl('');
      return undefined;
    }

    const objectUrl = URL.createObjectURL(
      selectedVideo
    );

    setVideoPreviewUrl(objectUrl);

    return () => {
      URL.revokeObjectURL(objectUrl);
    };
  }, [selectedVideo]);


  const analysisLabel = useMemo(() => {
    if (analysisState === 'running') {
      return 'Analyzing movement...';
    }

    if (analysisState === 'complete') {
      return 'Analysis complete';
    }

    return 'Start analysis';
  }, [analysisState]);


  const formScore =
    analysisResult?.form_score ?? 0;

  const formLabel = !analysisResult
    ? 'Waiting'
    : analysisResult.status === 'uncertain'
      ? 'Review'
      : formScore >= 75
        ? 'Good'
        : 'Needs review';

  const confidenceLabel = analysisResult
    ? `${Math.round(
        analysisResult.confidence * 100
      )}%`
    : '86%';


  const startAnalysis = async () => {
    setAnalysisState('running');
    setAnalysisError('');

    try {
      const body = new FormData();

      body.append(
        'exercise',
        'seated_leg_extension'
      );

      body.append(
        'session_id',
        sessionId
      );

      body.append(
        'source',
        selectedVideo ? 'upload' : 'demo'
      );

      if (selectedVideo) {
        body.append(
          'video',
          selectedVideo
        );
      }

      const response = await fetch(
        'http://127.0.0.1:8000/api/analyze-session',
        {
          method: 'POST',
          body,
        }
      );

      if (!response.ok) {
        throw new Error(
          `Backend returned ${response.status}`
        );
      }

      const result = await response.json();

      setAnalysisResult(result);
      setAnalysisState('complete');
    } catch (error) {
      setAnalysisState('error');

      setAnalysisError(
        'Backend unavailable. Start the local FastAPI server on port 8000.'
      );

      console.error(error);
    }
  };


  const saveCheckIn = async () => {
    setCheckinState('saving');
    setCheckinError('');

    try {
      const response = await fetch(
        `http://127.0.0.1:8000/api/sessions/${sessionId}/check-in`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            pain_score: pain,
            comment: patientComment,
            transcript_confidence: 0.79,
          }),
        }
      );

      if (!response.ok) {
        throw new Error(
          `Backend returned ${response.status}`
        );
      }

      setCheckinState('saved');
    } catch (error) {
      setCheckinState('error');

      setCheckinError(
        'Could not save check-in. Make sure the local backend is running.'
      );

      console.error(error);
    }
  };


  const saveDecision = async (decision) => {
    setDecisionState('saving');

    try {
      const response = await fetch(
        `http://127.0.0.1:8000/api/sessions/${sessionId}/decision`,
        {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
            decision,
            notes:
              decision === 'approve'
                ? 'Continue the existing therapist-approved protocol.'
                : 'Therapist requested changes.',
          }),
        }
      );

      if (!response.ok) {
        throw new Error(
          `Backend returned ${response.status}`
        );
      }

      setApproved(decision === 'approve');
      setDecisionState(decision);
    } catch (error) {
      setDecisionState('error');

      setAnalysisError(
        'Could not save therapist decision. Start the local FastAPI server.'
      );

      console.error(error);
    }
  };


  const chooseVideo = (event) => {
    const file = event.target.files?.[0];

    if (!file) {
      return;
    }

    setSelectedVideo(file);
    setAnalysisResult(null);
    setAnalysisState('ready');
    setAnalysisError('');
    setCheckinState('idle');
    setDecisionState('idle');
    setApproved(false);
  };


  return (
    <div className="app-shell">
      <aside
        className={`sidebar ${
          menuOpen ? 'sidebar-open' : ''
        }`}
      >
        <div className="brand-lockup">
          <div className="brand-mark">
            <Activity
              size={21}
              strokeWidth={2.4}
            />
          </div>

          <div>
            <div className="brand-name">
              Recovery Monitor
            </div>

            <div className="brand-product">
              NanoForge edge health
            </div>
          </div>
        </div>


        <div className="nav-label">
          Workspace
        </div>

        <nav className="nav-list">
          {[
            ['Overview', LayoutDashboard],
            ['Sessions', Clock3],
            ['Patients', UsersRound],
            ['Protocols', FileText],
          ].map(([label, Icon]) => (
            <button
              key={label}
              className={`nav-item ${
                activeNav === label ? 'active' : ''
              }`}
              onClick={() => {
                setActiveNav(label);
                setMenuOpen(false);
              }}
            >
              <Icon size={17} />
              <span>{label}</span>

              {label === 'Sessions' && (
                <span className="nav-count">
                  4
                </span>
              )}
            </button>
          ))}
        </nav>


        <div className="nav-label nav-label-lower">
          System
        </div>

        <nav className="nav-list">
          {[
            ['Model operations', Settings2],
            ['Privacy & runtime', LockKeyhole],
          ].map(([label, Icon]) => (
            <button
              key={label}
              className={`nav-item ${
                activeNav === label ? 'active' : ''
              }`}
              onClick={() => {
                setActiveNav(label);
                setMenuOpen(false);
              }}
            >
              <Icon size={17} />
              <span>{label}</span>
            </button>
          ))}
        </nav>


        <div className="sidebar-spacer" />

        <div className="runtime-card">
          <div className="runtime-topline">
            <span className="status-dot" />
            Local runtime ready
          </div>

          <div className="runtime-device">
            HP ZGX Nano
          </div>

          <div className="runtime-meta">
            Network not required
          </div>
        </div>


        <div className="user-row">
          <div className="avatar">
            AI
          </div>

          <div className="user-copy">
            <strong>Aishwarya Iyer</strong>
            <span>Therapist workspace</span>
          </div>

          <MoreHorizontal
            size={17}
            className="muted-icon"
          />
        </div>
      </aside>


      <main className="main-shell">
        <header className="topbar">
          <button
            className="mobile-menu"
            onClick={() => setMenuOpen(!menuOpen)}
          >
            <Menu size={21} />
          </button>

          <div className="breadcrumb">
            <span>Workspace</span>
            <ChevronRight size={14} />
            <strong>{activeNav}</strong>
          </div>

          <div className="topbar-actions">
            <div className="offline-pill">
              <WifiOff size={14} />
              Offline-capable
            </div>

            <button className="icon-button">
              <Bell size={18} />
            </button>

            <button className="help-button">
              <CircleHelp size={17} />
              Help
            </button>
          </div>
        </header>


        <div className="content-wrap">
          <div className="page-heading">
            <div>
              <div className="eyebrow">
                Wednesday, September 23, 2026
              </div>

              <h1>
                Good afternoon, Aishwarya
              </h1>

              <p className="page-subtitle">
                Review today's rehabilitation evidence before approving the next session.
              </p>
            </div>

            <button
              className="primary-button"
              onClick={() =>
                videoInputRef.current?.click()
              }
            >
              <Upload size={16} />
              New session
            </button>

            <input
              ref={videoInputRef}
              className="hidden-file-input"
              type="file"
              accept="video/*"
              onChange={chooseVideo}
            />
          </div>


          <section className="workflow-strip">
            {workflow.map((step, index) => {
              const Icon = step.icon;

              return (
                <div
                  className={`workflow-step ${
                    index < 2
                      ? 'complete'
                      : index === 2
                        ? 'current'
                        : ''
                  }`}
                  key={step.label}
                >
                  <div className="workflow-icon">
                    {index < 2 ? (
                      <Check size={15} />
                    ) : (
                      <Icon size={15} />
                    )}
                  </div>

                  <span>{step.label}</span>

                  {index < workflow.length - 1 && (
                    <div className="workflow-line" />
                  )}
                </div>
              );
            })}
          </section>


          <div className="privacy-banner">
            <LockKeyhole size={16} />

            <span>
              <strong>Private by design.</strong>{' '}
              All analysis is running locally on the HP ZGX Nano. No patient data leaves this device.
            </span>

            <button>
              View runtime details
              <ArrowUpRight size={14} />
            </button>
          </div>


          <section className="stats-grid">
            <StatCard
              label="Sessions this week"
              value="4"
              delta="+1 from last week"
              tone="blue"
              icon={Activity}
            />

            <StatCard
              label="Average form quality"
              value={
                analysisResult
                  ? `${formScore}%`
                  : '78%'
              }
              delta={
                analysisResult
                  ? 'This session'
                  : 'Improving'
              }
              tone="green"
              icon={HeartPulse}
            />

            <StatCard
              label="Pain trend"
              value="3.2 / 10"
              delta="Down 1.4 points"
              tone="purple"
              icon={MessageSquareText}
            />

            <StatCard
              label="Awaiting review"
              value="1"
              delta="Needs your attention"
              tone="amber"
              icon={ShieldCheck}
            />
          </section>


          <div className="dashboard-grid">
            <section className="panel analysis-panel">
              <PanelHeading
                title="Current session"
                meta="Today, 10:42 AM"
                action="Open session"
              />

              <div className="session-context">
                <div className="patient-mini">
                  <div className="patient-avatar">
                    JM
                  </div>

                  <div>
                    <strong>Jordan Mitchell</strong>
                    <span>
                      Post-knee rehabilitation · Week 3
                    </span>
                  </div>
                </div>

                <div className="exercise-tag">
                  <span className="tag-dot" />
                  Seated leg extension
                </div>
              </div>


              <div className="video-stage">
                <div className="video-toolbar">
                  <span className="recording-dot" />
                  Recorded exercise
                  <span className="video-time">
                    00:18 / 00:32
                  </span>
                </div>

                <div
                  className={`pose-scene ${
                    videoPreviewUrl
                      ? 'has-uploaded-video'
                      : ''
                  }`}
                >
                  {videoPreviewUrl ? (
                    <video
                      className="uploaded-video"
                      src={videoPreviewUrl}
                      controls
                      muted
                      playsInline
                    />
                  ) : (
                    <>
                      <div className="grid-lines" />

                      <div className="pose-card">
                        <div className="pose-head" />
                        <div className="pose-body" />
                        <div className="pose-leg pose-leg-back" />
                        <div className="pose-leg pose-leg-front" />
                        <div className="pose-foot" />
                        <div className="joint j-hip" />
                        <div className="joint j-knee" />
                        <div className="joint j-ankle" />
                      </div>

                      <div className="pose-label">
                        <span className="live-dot" />
                        Pose tracking active
                      </div>
                    </>
                  )}

                  <div className="angle-chip">
                    <span>
                      Range of motion
                    </span>

                    <strong>
                      {analysisResult
                        ? `${analysisResult.range_of_motion_deg}°`
                        : '62.4°'}
                    </strong>
                  </div>
                </div>

                <div className="video-footer">
                  <span>
                    <Video size={15} />
                    {selectedVideo
                      ? 'Uploaded video'
                      : 'Camera input'}
                  </span>

                  <span>
                    <LockKeyhole size={13} />
                    Local processing
                  </span>

                  <span className="video-status">
                    {selectedVideo
                      ? 'Video selected'
                      : 'Ready to review'}
                  </span>
                </div>
              </div>


              <div className="video-upload-row">
                <button
                  className="secondary-button"
                  onClick={() =>
                    videoInputRef.current?.click()
                  }
                >
                  <Upload size={15} />

                  {selectedVideo
                    ? 'Choose another video'
                    : 'Choose exercise video'}
                </button>

                <span>
                  {selectedVideo
                    ? `${selectedVideo.name} · ${(
                        selectedVideo.size /
                        1024 /
                        1024
                      ).toFixed(1)} MB`
                    : 'Optional for now — demo mode works without a file'}
                </span>
              </div>


              <div className="analysis-actions">
                <button
                  className="secondary-button"
                  onClick={() => {
                    setAnalysisResult(null);
                    setAnalysisState('ready');
                    setAnalysisError('');
                  }}
                >
                  <RotateCcw size={15} />
                  Re-run
                </button>

                <button
                  className={`primary-button analysis-button ${
                    analysisState === 'complete'
                      ? 'success-button'
                      : ''
                  }`}
                  onClick={startAnalysis}
                  disabled={analysisState === 'running'}
                >
                  {analysisState === 'complete' ? (
                    <Check size={16} />
                  ) : (
                    <Play size={16} />
                  )}

                  {analysisLabel}
                </button>
              </div>
            </section>


            <section className="panel evidence-panel">
              <PanelHeading
                title="Movement evidence"
                meta={`Model confidence ${confidenceLabel}`}
                action="Details"
              />

              <div className="quality-score">
                <div>
                  <span className="metric-label">
                    Form quality
                  </span>

                  <div className="score-line">
                    <strong>{formLabel}</strong>

                    <span className="confidence-pill">
                      {analysisResult
                        ? `${confidenceLabel} confidence`
                        : 'No result yet'}
                    </span>
                  </div>
                </div>

                <div className="score-ring">
                  <span>{formScore}</span>
                  <small>%</small>
                </div>
              </div>


              <div className="metric-list">
                <MetricRow
                  label="Repetitions"
                  value={`${analysisResult?.repetitions ?? 0} / ${targetRepetitions}`}
                  detail={
                    analysisResult
                      ? 'Detected locally'
                      : 'Waiting for analysis'
                  }
                  tone="green"
                />

                <MetricRow
                  label="Correct form"
                  value={`${analysisResult?.correct_repetitions ?? 0} / ${analysisResult?.repetitions ?? targetRepetitions}`}
                  detail={
                    analysisResult
                      ? `${Math.max(
                          0,
                          (analysisResult.repetitions ?? 0) -
                            (analysisResult.correct_repetitions ?? 0)
                        )} need review`
                      : 'Waiting for analysis'
                  }
                  tone="amber"
                />

                <MetricRow
                  label="Range of motion"
                  value={`${analysisResult?.range_of_motion_deg ?? 0}°`}
                  detail={
                    analysisResult
                      ? 'Observed knee range'
                      : 'Waiting for analysis'
                  }
                  tone="green"
                />

                <MetricRow
                  label="Movement smoothness"
                  value={
                    analysisResult
                      ? Number(
                          analysisResult.movement_smoothness
                        ).toFixed(2)
                      : '0.00'
                  }
                  detail={
                    analysisResult
                      ? analysisResult.movement_smoothness >= 0.8
                        ? 'Smooth'
                        : 'Moderate'
                      : 'Waiting for analysis'
                  }
                  tone="blue"
                />
              </div>


              <div className="evidence-card">
                <div className="evidence-title">
                  <Sparkles size={15} />
                  Evidence card
                  <span>
                    {analysisResult
                      ? 'Verified'
                      : 'Awaiting analysis'}
                  </span>
                </div>

                <p>
                  {analysisResult?.observations?.[0] ??
                    'Start analysis to generate movement evidence from the local control plane.'}{' '}
                  This is a form observation, not a clinical conclusion.
                </p>

                <button>
                  View frame evidence
                  <ArrowUpRight size={14} />
                </button>
              </div>


              <div className="uncertainty-note">
                <CircleHelp size={15} />

                <span>
                  <strong>Uncertainty:</strong>{' '}
                  {analysisResult?.observations?.[1] ??
                    'No movement confidence has been calculated yet.'}
                </span>
              </div>

              {analysisError && (
                <div className="backend-error">
                  <X size={14} />
                  {analysisError}
                </div>
              )}
            </section>
          </div>


          <div className="dashboard-grid lower-grid">
            <section className="panel trend-panel">
              <PanelHeading
                title="Recovery trajectory"
                meta="Last 3 sessions"
                action="View history"
              />

              <div className="trend-summary">
                <div>
                  <span className="metric-label">
                    Overall signal
                  </span>

                  <div className="trend-value">
                    <span className="trend-arrow">
                      ↗
                    </span>
                    Improving
                  </div>
                </div>

                <div className="trend-legend">
                  <span>
                    <i className="legend-line blue-line" />
                    Form quality
                  </span>

                  <span>
                    <i className="legend-line purple-line" />
                    Pain score
                  </span>
                </div>
              </div>

              <TrendChart />

              <div className="session-dates">
                <span>Sep 16</span>
                <span>Sep 19</span>
                <span>Sep 21</span>
                <span>Today</span>
              </div>

              <div className="trend-footnote">
                <CircleHelp size={14} />
                Trend is based on 4 sessions and should be reviewed with patient-reported context.
              </div>
            </section>


            <section className="panel checkin-panel">
              <PanelHeading
                title="Patient check-in"
                meta="Captured after session"
                action="Edit"
              />

              <div className="checkin-quote">
                <MessageSquareText size={18} />

                <textarea
                  value={patientComment}
                  onChange={(event) => {
                    setPatientComment(
                      event.target.value
                    );

                    setCheckinState('idle');
                  }}
                  aria-label="Patient comment"
                />
              </div>

              <div className="checkin-meta">
                <span>
                  <strong>Voice transcript</strong>{' '}
                  · Whisper local
                </span>

                <span className="confidence-pill">
                  0.79 confidence
                </span>
              </div>

              <div className="pain-heading">
                <strong>Reported pain</strong>
                <span>Select to correct if needed</span>
              </div>

              <div className="pain-scale">
                {[0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10].map((value) => (
                  <button
                    key={value}
                    className={pain === value ? "selected" : ""}
                    onClick={() => setPain(value)}
                  >
                    {value}
                  </button>
                ))}
              </div>

              <div className="pain-labels">
                <span>No pain</span>
                <span>Severe pain</span>
              </div>

              <button
                className="secondary-button checkin-save-button"
                onClick={saveCheckIn}
                disabled={checkinState === 'saving'}
              >
                {checkinState === 'saved' ? (
                  <Check size={14} />
                ) : (
                  <Upload size={14} />
                )}

                {checkinState === 'saving'
                  ? 'Saving check-in...'
                  : checkinState === 'saved'
                    ? 'Check-in saved'
                    : 'Save check-in'}
              </button>

              {checkinError && (
                <div className="backend-error">
                  <X size={14} />
                  {checkinError}
                </div>
              )}
            </section>
          </div>


          <section className="panel approval-panel">
            <div className="approval-copy">
              <div className="approval-icon">
                <ShieldCheck size={20} />
              </div>

              <div>
                <div className="eyebrow">
                  Therapist decision
                </div>

                <h2>
                  Review the next approved protocol step
                </h2>

                <p>
                  Based on the evidence, the system suggests continuing the existing seated leg-extension protocol with the same target range. No new exercise was generated.
                </p>

                <div className="approval-details">
                  <span>
                    <Check size={14} />
                    Within therapist-approved limits
                  </span>

                  <span>
                    <Check size={14} />
                    Pain below review threshold
                  </span>

                  <span>
                    <CircleHelp size={14} />
                    Confidence: medium-high
                  </span>
                </div>
              </div>
            </div>

            <div className="approval-actions">
              {approved ? (
                <div className="approved-state">
                  <Check size={17} />
                  Approved for next session
                </div>
              ) : (
                <>
                  <button
                    className="secondary-button"
                    onClick={() =>
                      saveDecision('request_changes')
                    }
                    disabled={decisionState === 'saving'}
                  >
                    <X size={15} />
                    Request changes
                  </button>

                  <button
                    className="primary-button"
                    onClick={() =>
                      saveDecision('approve')
                    }
                    disabled={decisionState === 'saving'}
                  >
                    <Check size={15} />
                    Approve protocol
                  </button>
                </>
              )}
            </div>
          </section>


          <footer className="app-footer">
            <span>
              Recovery Monitor is a therapist support tool, not medical advice.
            </span>

            <span>
              Model v0.1.0 · Local runtime ·{' '}
              <strong>Cloud AI disabled</strong>
            </span>
          </footer>
        </div>
      </main>
    </div>
  );
}


function StatCard({
  label,
  value,
  delta,
  tone,
  icon: Icon,
}) {
  return (
    <div className="stat-card">
      <div className={`stat-icon ${tone}`}>
        <Icon size={17} />
      </div>

      <div className="stat-copy">
        <span>{label}</span>
        <strong>{value}</strong>
        <small
          className={
            tone === 'amber'
              ? 'amber-text'
              : 'green-text'
          }
        >
          {delta}
        </small>
      </div>
    </div>
  );
}


function PanelHeading({
  title,
  meta,
  action,
}) {
  return (
    <div className="panel-heading">
      <div>
        <h2>{title}</h2>
        <span>{meta}</span>
      </div>

      <button className="text-button">
        {action}
        <ArrowUpRight size={14} />
      </button>
    </div>
  );
}


function MetricRow({
  label,
  value,
  detail,
  tone,
}) {
  return (
    <div className="metric-row">
      <div>
        <span>{label}</span>
        <small>{detail}</small>
      </div>

      <div className="metric-value">
        <strong>{value}</strong>
        <span className={`metric-dot ${tone}`} />
      </div>
    </div>
  );
}


function TrendChart() {
  return (
    <div className="chart-wrap">
      <svg
        viewBox="0 0 680 190"
        role="img"
        aria-label="Recovery trajectory chart"
      >
        <defs>
          <linearGradient
            id="areaBlue"
            x1="0"
            x2="0"
            y1="0"
            y2="1"
          >
            <stop
              offset="0%"
              stopColor="#2878d5"
              stopOpacity="0.18"
            />

            <stop
              offset="100%"
              stopColor="#2878d5"
              stopOpacity="0"
            />
          </linearGradient>
        </defs>

        <line
          x1="34"
          y1="26"
          x2="650"
          y2="26"
          className="chart-grid"
        />

        <line
          x1="34"
          y1="77"
          x2="650"
          y2="77"
          className="chart-grid"
        />

        <line
          x1="34"
          y1="128"
          x2="650"
          y2="128"
          className="chart-grid"
        />

        <text
          x="4"
          y="30"
          className="chart-label"
        >
          100
        </text>

        <text
          x="12"
          y="81"
          className="chart-label"
        >
          50
        </text>

        <text
          x="20"
          y="132"
          className="chart-label"
        >
          0
        </text>

        <path
          d="M34 120 C130 113, 155 109, 230 92 S350 91, 420 71 S550 71, 650 45 L650 145 L34 145 Z"
          fill="url(#areaBlue)"
        />

        <path
          d="M34 120 C130 113, 155 109, 230 92 S350 91, 420 71 S550 71, 650 45"
          className="chart-path blue-path"
        />

        <path
          d="M34 60 C130 72, 160 77, 230 82 S350 91, 420 103 S550 108, 650 117"
          className="chart-path purple-path"
        />

        <circle
          cx="34"
          cy="120"
          r="4"
          className="chart-point blue-point"
        />

        <circle
          cx="230"
          cy="92"
          r="4"
          className="chart-point blue-point"
        />

        <circle
          cx="420"
          cy="71"
          r="4"
          className="chart-point blue-point"
        />

        <circle
          cx="650"
          cy="45"
          r="5"
          className="chart-point blue-point"
        />

        <circle
          cx="34"
          cy="60"
          r="4"
          className="chart-point purple-point"
        />

        <circle
          cx="230"
          cy="82"
          r="4"
          className="chart-point purple-point"
        />

        <circle
          cx="420"
          cy="103"
          r="4"
          className="chart-point purple-point"
        />

        <circle
          cx="650"
          cy="117"
          r="5"
          className="chart-point purple-point"
        />
      </svg>
    </div>
  );
}


createRoot(
  document.getElementById('root')
).render(
  <StrictMode>
    <App />
  </StrictMode>
);