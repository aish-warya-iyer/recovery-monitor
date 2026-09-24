"""Physio side: review queue and decisions (#13, #36).

Safety gate: a session whose check-in pain is at or above the plan's threshold can't be approved
unless the physio explicitly confirms they reviewed the pain report (`acknowledge_pain: true`).
"""

import json
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app import db
from app.routes.common import flag_for, session_detail, session_summary

router = APIRouter(prefix="/api", tags=["review"])

SEVERITY_ORDER = {"urgent": 0, "review": 1, "none": 2}


@router.get("/review-queue")
def review_queue(include_reviewed: bool = False):
    """Analysed sessions that need a physio: flagged and not yet reviewed. Urgent first, then oldest."""
    rows = db.all_("SELECT * FROM sessions WHERE result_json IS NOT NULL ORDER BY created_at")
    out = []
    for r in rows:
        reviewed = db.one("SELECT 1 FROM reviews WHERE session_id = ?", r["id"]) is not None
        if reviewed and not include_reviewed:
            continue
        flag = flag_for(r)
        if not flag["flagged"] and not include_reviewed:
            continue
        patient = db.one("SELECT id, name FROM patients WHERE id = ?", r["patient_id"])
        out.append({**session_summary(r), "patient": patient, "reviewed": reviewed})
    out.sort(key=lambda x: (SEVERITY_ORDER[x["flag"]["severity"]], x["created_at"]))
    return out


class ReviewIn(BaseModel):
    decision: Literal["approve", "request_changes"]
    notes: str = ""
    rep_labels: dict[int, Literal["correct", "incorrect"]] = {}
    reference_video_id: int | None = None
    reviewer: str = "Physiotherapist"
    acknowledge_pain: bool = False


def store_review(session_id: str, body: ReviewIn) -> dict:
    s = db.one("SELECT * FROM sessions WHERE id = ?", session_id)
    if not s:
        raise HTTPException(404, "No such session")
    check_in = db.one("SELECT * FROM check_ins WHERE session_id = ?", session_id)
    protocol = db.one("SELECT * FROM protocols WHERE id = ?", s["protocol_id"]) if s["protocol_id"] else None
    threshold = protocol["pain_threshold"] if protocol else 5
    if body.decision == "approve" and check_in and check_in["pain_score"] >= threshold and not body.acknowledge_pain:
        raise HTTPException(409, f"Pain score {check_in['pain_score']}/10 is at or above the review threshold of "
                                 f"{threshold}/10. Confirm you reviewed the pain report (acknowledge_pain) to approve.")
    if body.reference_video_id and not db.one("SELECT id FROM reference_videos WHERE id = ?", body.reference_video_id):
        raise HTTPException(422, "Unknown reference video")
    result = db.loads(s["result_json"]) or {}
    n_reps = len(result.get("reps") or [])
    bad = [i for i in body.rep_labels if not 1 <= i <= n_reps]
    if bad:
        raise HTTPException(422, f"Rep numbers {bad} don't exist in this session ({n_reps} reps)")
    with db.tx() as c:
        c.execute("INSERT INTO reviews (session_id, decision, notes, rep_labels_json, reference_video_id, reviewer, "
                  "created_at) VALUES (?,?,?,?,?,?,?)",
                  (session_id, body.decision, body.notes, json.dumps({str(k): v for k, v in body.rep_labels.items()}),
                   body.reference_video_id, body.reviewer, db.now()))
    return session_detail(db.one("SELECT * FROM sessions WHERE id = ?", session_id))


@router.post("/sessions/{session_id}/review", status_code=201)
def review_session(session_id: str, body: ReviewIn):
    return store_review(session_id, body)


@router.get("/rep-corrections")
def rep_corrections():
    """Physio rep labels that disagree with the model: future training data (#30)."""
    out = []
    for r in db.all_("SELECT r.session_id, r.rep_labels_json, s.result_json FROM reviews r "
                     "JOIN sessions s ON s.id = r.session_id WHERE r.rep_labels_json != '{}'"):
        reps = {x["index"]: x for x in (db.loads(r["result_json"]) or {}).get("reps", [])}
        for idx, label in (db.loads(r["rep_labels_json"]) or {}).items():
            rep = reps.get(int(idx))
            if rep and rep["predicted_correct"] != (label == "correct"):
                out.append({"session_id": r["session_id"], "rep": int(idx), "physio_label": label,
                            "model_probability_incorrect": rep["probability_incorrect"]})
    return out
