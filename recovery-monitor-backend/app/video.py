"""Upload handling (#33): normalize any phone/webcam video to H.264 MP4 so analysis and every browser
can read it, and grab a thumbnail. Uses the ffmpeg binary bundled with imageio-ffmpeg (no system install)."""

import re
import subprocess
from pathlib import Path

import imageio_ffmpeg

FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()
MAX_HEIGHT = 1080


class VideoError(ValueError):
    pass


def probe_duration(path: Path) -> float | None:
    out = subprocess.run([FFMPEG, "-hide_banner", "-i", str(path)], capture_output=True, text=True).stderr
    m = re.search(r"Duration: (\d+):(\d+):(\d+(?:\.\d+)?)", out)
    if not m:
        return None
    h, mnt, s = m.groups()
    return int(h) * 3600 + int(mnt) * 60 + float(s)


def normalize(src: Path, dst: Path) -> float:
    """Transcode to H.264/yuv420p MP4, max 1080p tall, constant 30 fps, no audio. Returns duration in s."""
    dur = probe_duration(src)
    if dur is None:
        raise VideoError("This file doesn't look like a video we can read.")
    if dur < 1.0:
        raise VideoError("The video is shorter than one second.")
    cmd = [FFMPEG, "-y", "-loglevel", "error", "-i", str(src), "-an",
           "-vf", f"scale='trunc(iw*min(1,{MAX_HEIGHT}/ih)/2)*2':'trunc(min(ih,{MAX_HEIGHT})/2)*2',fps=30",
           "-c:v", "libx264", "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p",
           "-movflags", "+faststart", str(dst)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode or not dst.exists():
        raise VideoError(f"Could not convert the video: {r.stderr.strip()[:200]}")
    return dur


def thumbnail(src: Path, dst: Path, at_s: float = 1.0) -> Path | None:
    r = subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-ss", str(at_s), "-i", str(src), "-frames:v", "1",
                        "-vf", "scale=480:-2", str(dst)], capture_output=True)
    return dst if r.returncode == 0 and dst.exists() else None


def clip(src: Path, dst: Path, start_s: float, end_s: float) -> None:
    """Cut [start_s, end_s] into a new H.264 MP4 (used to build reference clips and demo sessions)."""
    r = subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-ss", f"{start_s:.2f}", "-to", f"{end_s:.2f}",
                        "-i", str(src), "-an", "-vf", f"scale=-2:'min(ih,{MAX_HEIGHT})',fps=30", "-c:v", "libx264",
                        "-preset", "veryfast", "-crf", "23", "-pix_fmt", "yuv420p", "-movflags", "+faststart",
                        str(dst)], capture_output=True, text=True)
    if r.returncode:
        raise VideoError(r.stderr.strip()[:200])

