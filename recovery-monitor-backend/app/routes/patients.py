"""Patients and their protocol versions (#35). A protocol change creates a new version; the latest
version is the current plan."""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app import db
from app.routes.common import session_summary

router = APIRouter(prefix="/api/patients", tags=["patients"])

EXERCISES = ("squat", "seated_leg_extension")


class ProtocolIn(BaseModel):
    exercise: str = Field("squat", pattern="^(squat|seated_leg_extension)$")
    target_reps: int = Field(10, ge=1, le=100)
    target_depth_deg: float = Field(100, ge=30, le=175, description="knee angle at the bottom; smaller = deeper")
    pain_threshold: int = Field(5, ge=0, le=10)
    tempo: str | None = "Slow and controlled"
    reference_video_id: int | None = None
    notes: str | None = None
    approved_by: str = "Physiotherapist"


class PatientIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    condition: str | None = None
    id: str | None = Field(None, pattern="^[a-z0-9-]{2,40}$")


def current_protocol(patient_id: str) -> dict | None:
    return db.one("SELECT * FROM protocols WHERE patient_id = ? ORDER BY version DESC LIMIT 1", patient_id)


def _patient_or_404(patient_id: str) -> dict:
    p = db.one("SELECT * FROM patients WHERE id = ?", patient_id)
    if not p:
        raise HTTPException(404, "No such patient")
    return p


@router.get("")
def list_patients():
    out = []
    for p in db.all_("SELECT * FROM patients ORDER BY name"):
        last = db.one("SELECT created_at FROM sessions WHERE patient_id = ? ORDER BY created_at DESC LIMIT 1", p["id"])
        pending = db.one("SELECT COUNT(*) n FROM sessions s WHERE patient_id = ? AND result_json IS NOT NULL AND "
                         "NOT EXISTS (SELECT 1 FROM reviews r WHERE r.session_id = s.id)", p["id"])["n"]
        out.append({**p, "protocol": current_protocol(p["id"]), "last_session_at": last and last["created_at"],
                    "sessions_awaiting_review": pending})
    return out


@router.post("", status_code=201)
def create_patient(body: PatientIn):
    import uuid

    pid = body.id or uuid.uuid4().hex[:8]
    if db.one("SELECT id FROM patients WHERE id = ?", pid):
        raise HTTPException(409, "A patient with this id already exists")
    with db.tx() as c:
        c.execute("INSERT INTO patients (id, name, condition, created_at) VALUES (?,?,?,?)",
                  (pid, body.name, body.condition, db.now()))
    return get_patient(pid)


@router.get("/{patient_id}")
def get_patient(patient_id: str):
    return {**_patient_or_404(patient_id), "protocol": current_protocol(patient_id)}


@router.get("/{patient_id}/protocol")
def get_protocol(patient_id: str):
    _patient_or_404(patient_id)
    return current_protocol(patient_id)


@router.get("/{patient_id}/protocol/history")
def protocol_history(patient_id: str):
    _patient_or_404(patient_id)
    return db.all_("SELECT * FROM protocols WHERE patient_id = ? ORDER BY version DESC", patient_id)


@router.post("/{patient_id}/protocol", status_code=201)
def set_protocol(patient_id: str, body: ProtocolIn):
    _patient_or_404(patient_id)
    if body.reference_video_id and not db.one("SELECT id FROM reference_videos WHERE id = ?", body.reference_video_id):
        raise HTTPException(422, "Unknown reference video")
    prev = current_protocol(patient_id)
    with db.tx() as c:
        c.execute(
            "INSERT INTO protocols (patient_id, version, exercise, target_reps, target_depth_deg, pain_threshold, "
            "tempo, reference_video_id, notes, approved_by, created_at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
            (patient_id, (prev["version"] + 1) if prev else 1, body.exercise, body.target_reps, body.target_depth_deg,
             body.pain_threshold, body.tempo, body.reference_video_id, body.notes, body.approved_by, db.now()))
    return current_protocol(patient_id)


@router.get("/{patient_id}/sessions")
def patient_sessions(patient_id: str):
    """Session history, oldest first, with the numbers the trend chart needs."""
    _patient_or_404(patient_id)
    rows = db.all_("SELECT * FROM sessions WHERE patient_id = ? ORDER BY created_at", patient_id)
    return [session_summary(r) for r in rows]
