"""Patient issue intake and therapist-approved exercise-plan workflow."""

import json
import uuid

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, Field

from app import db
from app.auth import current_user

router = APIRouter(prefix="/api", tags=["intakes"])
EXERCISES = {"arm_abduction", "arm_vw", "push_ups", "leg_abduction", "leg_lunge", "squat"}


class IntakeIn(BaseModel):
    affected_areas: list[str] = Field(min_length=1, max_length=10)
    issue_types: list[str] = Field(min_length=1, max_length=10)
    when_it_happens: list[str] = Field(default_factory=list, max_length=10)
    pain_score: int = Field(ge=0, le=10)
    duration: str = Field(min_length=1, max_length=40)
    trend: str = Field(min_length=1, max_length=30)
    limitations: list[str] = Field(default_factory=list, max_length=10)
    goals: list[str] = Field(min_length=1, max_length=10)
    notes: str | None = Field(None, max_length=2000)


class PlanIn(BaseModel):
    exercise: str
    reference_video_id: int | None = None
    target_reps: int = Field(ge=1, le=100)
    target_sets: int = Field(ge=1, le=20)
    target_depth_deg: float | None = Field(None, ge=30, le=175)
    pain_threshold: int = Field(ge=0, le=10)
    instructions: str | None = Field(None, max_length=2000)
    notes: str | None = Field(None, max_length=2000)


class DecisionIn(BaseModel):
    notes: str | None = Field(None, max_length=2000)


def _json(value):
    return json.dumps(value, separators=(",", ":"))


def _intake(row: dict) -> dict:
    if not row:
        raise HTTPException(404, "No such intake")
    result = dict(row)
    for key in ("affected_areas_json", "issue_types_json", "when_it_happens_json", "limitations_json", "goals_json"):
        result[key.removesuffix("_json")] = json.loads(result.pop(key))
    plan = db.one("SELECT * FROM plan_drafts WHERE intake_id=? ORDER BY created_at DESC LIMIT 1", row["id"])
    result["plan"] = plan
    result["patient"] = db.one("SELECT u.id, u.email, pp.name FROM users u LEFT JOIN patient_profiles pp ON pp.user_id=u.id WHERE u.id=?", row["patient_user_id"])
    return result


def _therapist(user: dict) -> None:
    if user["role"] != "therapist":
        raise HTTPException(403, "Therapist account required")


@router.post("/patient/intakes", status_code=201)
def create_intake(body: IntakeIn, request: Request):
    user = current_user(request)
    if user["role"] != "patient":
        raise HTTPException(403, "Patient account required")
    if not db.one("SELECT 1 FROM patient_profiles WHERE user_id=? AND completed_at IS NOT NULL", user["id"]):
        raise HTTPException(409, "Complete patient onboarding first")
    intake_id = f"intake-{uuid.uuid4().hex[:12]}"
    now = db.now()
    with db.tx() as c:
        c.execute("INSERT INTO patient_intakes (id,patient_user_id,affected_areas_json,issue_types_json,when_it_happens_json,"
                  "pain_score,duration,trend,limitations_json,goals_json,notes,status,created_at,updated_at) "
                  "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (intake_id, user["id"], _json(body.affected_areas), _json(body.issue_types), _json(body.when_it_happens),
                   body.pain_score, body.duration, body.trend, _json(body.limitations), _json(body.goals), body.notes,
                   "pending", now, now))
    return _intake(db.one("SELECT * FROM patient_intakes WHERE id=?", intake_id))


@router.get("/patient/intakes")
def patient_intakes(request: Request):
    user = current_user(request)
    if user["role"] != "patient":
        raise HTTPException(403, "Patient account required")
    return [_intake(row) for row in db.all_("SELECT * FROM patient_intakes WHERE patient_user_id=? ORDER BY created_at DESC", user["id"])]


@router.get("/therapist/intakes")
def therapist_intakes(request: Request, status: str | None = None):
    user = current_user(request)
    _therapist(user)
    sql = "SELECT * FROM patient_intakes WHERE (assigned_therapist_id IS NULL OR assigned_therapist_id=?) AND NOT EXISTS (SELECT 1 FROM therapist_intake_decisions d WHERE d.intake_id=patient_intakes.id AND d.therapist_user_id=? AND d.decision='declined')"
    args = [user["id"], user["id"]]
    if status:
        sql += " AND status=?"
        args.append(status)
    sql += " ORDER BY created_at DESC"
    return [_intake(row) for row in db.all_(sql, *args)]


@router.get("/therapist/intakes/{intake_id}")
def therapist_intake(intake_id: str, request: Request):
    user = current_user(request)
    _therapist(user)
    row = db.one("SELECT * FROM patient_intakes WHERE id=? AND (assigned_therapist_id IS NULL OR assigned_therapist_id=?)",
                 intake_id, user["id"])
    return _intake(row)


@router.post("/therapist/intakes/{intake_id}/plan", status_code=201)
def create_plan(intake_id: str, body: PlanIn, request: Request):
    user = current_user(request)
    _therapist(user)
    if body.exercise not in EXERCISES:
        raise HTTPException(422, "Unsupported exercise")
    intake = db.one("SELECT * FROM patient_intakes WHERE id=? AND (assigned_therapist_id IS NULL OR assigned_therapist_id=?)",
                    intake_id, user["id"])
    if not intake:
        raise HTTPException(404, "No accessible intake")
    if body.reference_video_id and not db.one("SELECT id FROM reference_videos WHERE id=?", body.reference_video_id):
        raise HTTPException(422, "Unknown reference video")
    plan_id = f"plan-{uuid.uuid4().hex[:12]}"
    now = db.now()
    with db.tx() as c:
        c.execute("INSERT INTO plan_drafts (id,intake_id,therapist_user_id,exercise,reference_video_id,target_reps,target_sets,"
                  "target_depth_deg,pain_threshold,instructions,notes,status,created_at,updated_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (plan_id, intake_id, user["id"], body.exercise, body.reference_video_id, body.target_reps, body.target_sets,
                   body.target_depth_deg, body.pain_threshold, body.instructions, body.notes, "plan_drafted", now, now))
        c.execute("UPDATE patient_intakes SET assigned_therapist_id=?, status='plan_drafted', updated_at=? WHERE id=?",
                  (user["id"], now, intake_id))
    return db.one("SELECT * FROM plan_drafts WHERE id=?", plan_id)


def _decision(plan_id: str, action: str, body: DecisionIn, request: Request):
    user = current_user(request)
    _therapist(user)
    plan = db.one("SELECT * FROM plan_drafts WHERE id=? AND therapist_user_id=?", plan_id, user["id"])
    if not plan:
        raise HTTPException(404, "No accessible plan")
    status = "approved" if action == "approve" else "changes_requested"
    now = db.now()
    with db.tx() as c:
        c.execute("UPDATE plan_drafts SET status=?, updated_at=? WHERE id=?", (status, now, plan_id))
        c.execute("UPDATE patient_intakes SET status=?, updated_at=? WHERE id=?", (status, now, plan["intake_id"]))
        c.execute("INSERT INTO plan_approvals (plan_id,therapist_user_id,action,notes,created_at) VALUES (?,?,?,?,?)",
                  (plan_id, user["id"], action, body.notes, now))
    return db.one("SELECT * FROM plan_drafts WHERE id=?", plan_id)


@router.post("/therapist/plans/{plan_id}/approve")
def approve_plan(plan_id: str, body: DecisionIn, request: Request):
    return _decision(plan_id, "approve", body, request)


@router.post("/therapist/plans/{plan_id}/request-changes")
def request_changes(plan_id: str, body: DecisionIn, request: Request):
    return _decision(plan_id, "request_changes", body, request)

@router.get("/patient/care-team")
def patient_care_team(request: Request):
    user = current_user(request)
    if user["role"] != "patient":
        raise HTTPException(403, "Patient account required")
    rows = db.all_("SELECT DISTINCT u.id, u.email, tp.name FROM patient_intakes i JOIN users u ON u.id=i.assigned_therapist_id LEFT JOIN therapist_profiles tp ON tp.user_id=u.id WHERE i.patient_user_id=? AND i.assigned_therapist_id IS NOT NULL ORDER BY i.updated_at DESC", user["id"])
    return {"therapist": rows[0] if rows else None}

@router.post("/therapist/intakes/{intake_id}/claim")
def claim_intake(intake_id: str, request: Request):
    user = current_user(request)
    _therapist(user)
    intake = db.one("SELECT * FROM patient_intakes WHERE id=?", intake_id)
    if not intake:
        raise HTTPException(404, "No such intake")
    if intake["assigned_therapist_id"] and intake["assigned_therapist_id"] != user["id"]:
        raise HTTPException(409, "This patient already has a therapist")
    with db.tx() as c:
        c.execute("UPDATE patient_intakes SET assigned_therapist_id=?, status='under_review', updated_at=? WHERE id=?", (user["id"], db.now(), intake_id))
        c.execute("INSERT OR REPLACE INTO therapist_intake_decisions (intake_id,therapist_user_id,decision,created_at) VALUES (?,?,?,?)", (intake_id, user["id"], "accepted", db.now()))
    return _intake(db.one("SELECT * FROM patient_intakes WHERE id=?", intake_id))

@router.post("/therapist/intakes/{intake_id}/decline")
def decline_intake(intake_id: str, request: Request):
    user = current_user(request)
    _therapist(user)
    if not db.one("SELECT id FROM patient_intakes WHERE id=?", intake_id):
        raise HTTPException(404, "No such intake")
    with db.tx() as c:
        c.execute("INSERT OR REPLACE INTO therapist_intake_decisions (intake_id,therapist_user_id,decision,created_at) VALUES (?,?,?,?)", (intake_id, user["id"], "declined", db.now()))
    return {"id": intake_id, "decision": "declined"}
