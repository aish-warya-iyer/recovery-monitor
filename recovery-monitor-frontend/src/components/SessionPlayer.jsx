import { forwardRef, useEffect, useImperativeHandle, useRef, useState } from 'react';
import AngleChart from './AngleChart.jsx';

// Video (annotated or original) with the knee-angle chart underneath, kept in sync both ways.
const SessionPlayer = forwardRef(function SessionPlayer({ session, selectedRep, onTime }, ref) {
  const video = useRef(null);
  const [time, setTime] = useState(0);
  const [annotated, setAnnotated] = useState(Boolean(session.annotated_video_url));
  const result = session.result;
  const src = annotated && session.annotated_video_url ? session.annotated_video_url : session.video_url;

  useImperativeHandle(ref, () => ({
    seek: (t) => {
      if (video.current) {
        video.current.currentTime = t;
        setTime(t);
      }
    },
  }));

  useEffect(() => {
    let raf;
    const tick = () => {
      if (video.current) {
        const t = video.current.currentTime;
        setTime(t);
        onTime?.(t);
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => cancelAnimationFrame(raf);
  }, [onTime]);

  if (!src) return <div className="empty-note">The video is still being prepared.</div>;

  return (
    <div className="session-player">
      <div className="video-frame">
        <video ref={video} src={src} controls playsInline preload="metadata" />
      </div>
      {session.annotated_video_url && (
        <div className="segmented small">
          <button className={annotated ? 'on' : ''} onClick={() => setAnnotated(true)}>With pose overlay</button>
          <button className={!annotated ? 'on' : ''} onClick={() => setAnnotated(false)}>Original</button>
        </div>
      )}
      {result?.angle_series && (
        <>
          <div className="chart-caption">
            <span>Knee angle ({result.metrics?.side ?? 'measured'} leg)</span>
            {result.metrics?.expected_angle_error_deg != null && (
              <span className="muted">±{Math.round(result.metrics.expected_angle_error_deg)}° measured error for this camera angle</span>
            )}
          </div>
          <AngleChart
            series={result.angle_series}
            reps={result.reps}
            targetDepth={result.protocol?.target_depth_deg}
            currentTime={time}
            selectedRep={selectedRep}
            onSeek={(t) => {
              if (video.current) video.current.currentTime = t;
            }}
          />
        </>
      )}
    </div>
  );
});

export default SessionPlayer;
