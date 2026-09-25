"""Patient sessions: upload a video, follow progress, fetch results and media, check in, delete (#13, #33, #38)."""

import asyncio
import json
import shutil
import uuid
from pathlib import Path

from fastapi import APIRouter, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from app import db, jobs
from app.config import ALLOWED_VIDEO_TYPES, MAX_UPLOAD_MB, VIDEO_DIR
from app.routes.common import session_detail
from app.routes.patients import current_protocol

router = APIRouter(prefix="/api", tags=["sessions"])


def _session_or_404(session_id: str) -> dict:
    s = db.one("SELECT * FROM sessions WHERE id = ?", session_id)
    if not s:
        raise HTTPException(404, "No such session")
    return s


async def save_upload(video: UploadFile, dest_dir: Path) -> Path:
    suffix = Path(video.filename or "video.mp4").suffix.lower() or ".mp4"
    if suffix not in ALLOWED_VIDEO_TYPES:
        raise HTTPException(415, f"Unsupported file type {suffix}. Upload an MP4, MOV or WebM video.")
    dest_dir.mkdir(parents=True, exist_ok=True)
    raw = dest_dir / f"upload{suffix}"
    size = 0
    with raw.open("wb") as f:
        while chunk := await video.read(1 << 20):
            size += len(chunk)
            if size > MAX_UPLOAD_MB << 20:
                f.close()
                shutil.rmtree(dest_dir, ignore_errors=True)
                raise HTTPException(413, f"Video is larger than {MAX_UPLOAD_MB} MB.")
            f.write(chunk)
    return raw


def create_session(patient_id: str, source: str, raw: Path, session_id: str, created_at: str | None = None) -> dict:
    protocol = current_protocol(patient_id)
    ts = created_at or db.now()
    with db.tx() as c:
        c.execute("INSERT INTO sessions (id, patient_id, protocol_id, exercise, status, stage, progress, source, "
                  "created_at, updated_at) VALUES (?,?,?,?, 'uploaded', 'queued', 0, ?, ?, ?)",
                  (session_id, patient_id, protocol and protocol["id"], protocol["exercise"] if protocol else "squat",
                   source, ts, ts))
    jobs.submit(session_id, raw)
    return {"session_id": session_id, "status": "uploaded"}


@router.post("/patients/{patient_id}/sessions", status_code=202)
async def upload_session(patient_id: str, video: UploadFile = File(...), source: str = Form("upload")):
    if not db.one("SELECT id FROM patients WHERE id = ?", patient_id):
        raise HTTPException(404, "No such patient")
    if source not in ("upload", "camera", "demo"):
        raise HTTPException(422, "source must be upload, camera or demo")
    session_id = uuid.uuid4().hex[:12]
    raw = await save_upload(video, VIDEO_DIR / session_id)
    return create_session(patient_id, source, raw, session_id)


@router.get("/sessions/{session_id}")
def get_session(session_id: str):
    return session_detail(_session_or_404(session_id))


@router.get("/sessions/{session_id}/events")
async def session_events(session_id: str, request: Request):
    """Server-Sent Events: one `progress` event per change, then a final `done` or `failed` event."""
    _session_or_404(session_id)

    async def stream():
        last = None
        while not await request.is_disconnected():
            s = db.one("SELECT status, stage, progress, error FROM sessions WHERE id = ?", session_id)
            if s is None:
                return
            if s != last:
                yield f"event: progress\ndata: {json.dumps(s)}\n\n"
                last = s
            if s["stage"] in ("done", "failed"):
                yield f"event: {s['stage']}\ndata: {json.dumps(s)}\n\n"
                return
            await asyncio.sleep(0.5)

    return StreamingResponse(stream(), media_type="text/event-stream", headers={"Cache-Control": "no-cache"})


def _file(path: str | None, media_type: str):
    if not path or not Path(path).exists():
        raise HTTPException(404, "Not available yet")
    return FileResponse(path, media_type=media_type)


@router.get("/sessions/{session_id}/video")
def session_video(session_id: str):
    return _file(_session_or_404(session_id)["video_path"], "video/mp4")


@router.get("/sessions/{session_id}/annotated-video")
def session_annotated(session_id: str):
    return _file(_session_or_404(session_id)["annotated_path"], "video/mp4")


@router.get("/sessions/{session_id}/thumbnail")
def session_thumbnail(session_id: str):
    return _file(_session_or_404(session_id)["thumbnail_path"], "image/jpeg")


class CheckIn(BaseModel):
    pain_score: int = Field(ge=0, le=10)
    stiffness: bool | None = None
    comment: str = ""
    transcript: str | None = None
    transcript_confidence: float | None = Field(default=None, ge=0, le=1)  # accepted for the current UI


@router.post("/patients/{patient_id}/sessions/{session_id}/check-in")
def save_check_in(patient_id: str, session_id: str, body: CheckIn):
    s = _session_or_404(session_id)
    if s["patient_id"] != patient_id:
        raise HTTPException(404, "No such session for this patient")
    return _store_check_in(session_id, body)


@router.post("/patients/{patient_id}/sessions/{session_id}/voice")
async def voice_note(patient_id: str, session_id: str, audio: UploadFile = File(...)):
    """Patient's spoken description -> text with Whisper on this device. Returned for the patient to confirm;
    it is stored only when they submit the check-in."""
    s = _session_or_404(session_id)
    if s["patient_id"] != patient_id:
        raise HTTPException(404, "No such session for this patient")
    folder = VIDEO_DIR / session_id
    folder.mkdir(parents=True, exist_ok=True)
    raw = folder / f"voice{Path(audio.filename or 'voice.webm').suffix or '.webm'}"
    raw.write_bytes(await audio.read())
    return await asyncio.to_thread(_transcribe, raw)


def _transcribe(raw: Path) -> dict:
    import subprocess

    import httpx

    from app.config import AI_SERVICE_URL
    from app.video import FFMPEG

    wav = raw.with_suffix(".wav")
    r = subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", str(raw), "-ac", "1", "-ar", "16000", str(wav)],
                       capture_output=True, text=True)
    if r.returncode or not wav.exists():
        raise HTTPException(422, "Could not read the recording.")
    try:
        res = httpx.post(f"{AI_SERVICE_URL}/asr", json={"path": str(wav)}, timeout=120)
        res.raise_for_status()
    except httpx.HTTPStatusError as e:
        raise HTTPException(e.response.status_code, e.response.json().get("detail", "Transcription failed")) from e
    except httpx.HTTPError as e:
        raise HTTPException(503, "The on-device speech model is not running.") from e
    return res.json() | {"model": "whisper-large-v3-turbo (on this device)"}


def _store_check_in(session_id: str, body: CheckIn) -> dict:
    with db.tx() as c:
        c.execute("INSERT INTO check_ins (session_id, pain_score, stiffness, comment, transcript, created_at) "
                  "VALUES (?,?,?,?,?,?) ON CONFLICT(session_id) DO UPDATE SET pain_score=excluded.pain_score, "
                  "stiffness=excluded.stiffness, comment=excluded.comment, transcript=excluded.transcript, "
                  "created_at=excluded.created_at",
                  (session_id, body.pain_score, None if body.stiffness is None else int(body.stiffness),
                   body.comment, body.transcript, db.now()))
    s = _session_or_404(session_id)
    if s["result_json"]:
        from app.jobs import submit_report

        submit_report(session_id)  # the patient's words change the report
    return session_detail(s)


@router.delete("/sessions/{session_id}", status_code=204)
def delete_session(session_id: str):
    """Removes the video, annotated video, thumbnail and all results for this session (#38)."""
    _session_or_404(session_id)
    shutil.rmtree(VIDEO_DIR / session_id, ignore_errors=True)
    with db.tx() as c:
        c.execute("DELETE FROM reviews WHERE session_id = ?", (session_id,))
        c.execute("DELETE FROM reports WHERE session_id = ?", (session_id,))
        c.execute("DELETE FROM check_ins WHERE session_id = ?", (session_id,))
        c.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
