"""Endpoints the current single-page UI calls. Kept so the existing screens work while the new
patient/physio portals are built on the /api/patients and /api/review-queue endpoints.

Fix vs the original: the pain safety gate checked `payload.decision` inside the *check-in* endpoint
(check-ins have no decision field, so every check-in raised a 500). It now lives on the decision
endpoint where it belongs.
"""

import asyncio
import json
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field

from app.config import REPO_ROOT

router = APIRouter(prefix="/api", tags=["legacy"])

PAIN_REVIEW_THRESHOLD = 4
FIXTURE = REPO_ROOT / "fixtures" / "analysis_result.json"


class CheckInRequest(BaseModel):
    pain_score: int = Field(ge=0, le=10)
    comment: str = ""
    transcript_confidence: float | None = Field(default=None, ge=0, le=1)


class DecisionRequest(BaseModel):
    decision: Literal["approve", "request_changes"]
    notes: str = ""


SESSION_RECORDS: dict[str, dict] = {}


def _now():
    return datetime.now(timezone.utc).isoformat()


@router.post("/sessions/{session_id}/check-in")
async def legacy_check_in(session_id: str, payload: CheckInRequest):
    rec = SESSION_RECORDS.get(session_id, {"session_id": session_id, "check_in": None, "decision": None})
    rec.update(check_in=payload.model_dump(), updated_at=_now())
    SESSION_RECORDS[session_id] = rec
    return rec


@router.post("/sessions/{session_id}/decision")
async def legacy_decision(session_id: str, payload: DecisionRequest):
    rec = SESSION_RECORDS.get(session_id, {"session_id": session_id, "check_in": None, "decision": None})
    check_in = rec.get("check_in")
    if payload.decision == "approve" and check_in and check_in["pain_score"] > PAIN_REVIEW_THRESHOLD:
        raise HTTPException(409, f"Pain score is above the review threshold of {PAIN_REVIEW_THRESHOLD}/10. "
                                 "Therapist review is required.")
    rec.update(decision=payload.model_dump(), updated_at=_now())
    SESSION_RECORDS[session_id] = rec
    return rec


@router.post("/analyze-session")
async def legacy_analyze(
    exercise: Literal["seated_leg_extension", "squat"] = Form("seated_leg_extension"),
    session_id: str = Form("demo-session-001"),
    source: Literal["demo", "upload", "camera"] = Form("demo"),
    video: UploadFile | None = File(None),
):
    """Synchronous analysis. With no video, returns the real fixture (pipeline output on public
    sample data) instead of made-up numbers."""
    if video is None:
        result = json.loads(FIXTURE.read_text())
        result.pop("_fixture_note", None)
        result.update(session_id=session_id, source=source, origin=result["origin"] + "_sample")
        return result
    suffix = Path(video.filename or "exercise.mp4").suffix or ".mp4"
    with tempfile.NamedTemporaryFile(suffix=suffix) as tmp:
        tmp.write(await video.read())
        tmp.flush()
        if exercise == "squat":
            from model.analyze import analyze_video

            result = await asyncio.to_thread(analyze_video, tmp.name, "squat", None)
        else:
            from app.legacy import analyze_uploaded_video

            result = await asyncio.to_thread(analyze_uploaded_video, tmp.name)
            result["origin"] = "local_mediapipe_heuristic"
    result.update(session_id=session_id, exercise=exercise, source=source, analyzed_at=result.get("analyzed_at", _now()))
    return result
