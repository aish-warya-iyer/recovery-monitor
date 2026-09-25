"""Authentication and role-specific onboarding endpoints."""

import uuid

from fastapi import APIRouter, HTTPException, Request, Response
from pydantic import BaseModel, Field

from app import db
from app.auth import SESSION_COOKIE, create_session, current_user, drop_session, hash_password, public_user, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])
onboarding_router = APIRouter(prefix="/api/onboarding", tags=["onboarding"])


class SignupIn(BaseModel):
    email: str = Field(min_length=3, max_length=255)
    password: str = Field(min_length=8, max_length=200)
    role: str = Field(pattern="^(patient|therapist)$")


class LoginIn(BaseModel):
    email: str
    password: str


class PatientOnboardingIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    affected_areas: list[str] = Field(default_factory=list, max_length=10)
    goals: list[str] = Field(default_factory=list, max_length=10)
    consent_local_analysis: bool = False


class TherapistOnboardingIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    specializations: list[str] = Field(default_factory=list, max_length=20)
    supported_exercises: list[str] = Field(default_factory=list, max_length=20)


def _completed(user: dict) -> bool:
    table = "patient_profiles" if user["role"] == "patient" else "therapist_profiles"
    return db.one(f"SELECT 1 FROM {table} WHERE user_id=? AND completed_at IS NOT NULL", user["id"]) is not None


def _result(user: dict) -> dict:
    table = "patient_profiles" if user["role"] == "patient" else "therapist_profiles"
    return {"user": public_user(user), "profile": db.one(f"SELECT * FROM {table} WHERE user_id=?", user["id"]),
            "onboarding_completed": _completed(user)}


@router.post("/signup", status_code=201)
def signup(body: SignupIn, response: Response):
    email = body.email.strip().lower()
    if db.one("SELECT id FROM users WHERE email=?", email):
        raise HTTPException(409, "An account with this email already exists")
    user_id = f"user-{uuid.uuid4().hex[:12]}"
    with db.tx() as c:
        c.execute("INSERT INTO users (id,email,password_hash,role,created_at) VALUES (?,?,?,?,?)",
                  (user_id, email, hash_password(body.password), body.role, db.now()))
    user = db.one("SELECT * FROM users WHERE id=?", user_id)
    response.set_cookie(SESSION_COOKIE, create_session(user_id), httponly=True, samesite="lax", max_age=30 * 86400)
    return _result(user)


@router.post("/login")
def login(body: LoginIn, response: Response):
    user = db.one("SELECT * FROM users WHERE email=?", body.email.strip().lower())
    if not user or not verify_password(body.password, user["password_hash"]):
        raise HTTPException(401, "Invalid email or password")
    response.set_cookie(SESSION_COOKIE, create_session(user["id"]), httponly=True, samesite="lax", max_age=30 * 86400)
    return _result(user)


@router.get("/me")
def me(request: Request):
    return _result(current_user(request))


@router.post("/logout", status_code=204)
def logout(request: Request, response: Response):
    drop_session(request)
    response.delete_cookie(SESSION_COOKIE)


@onboarding_router.get("")
def get_onboarding(request: Request):
    return _result(current_user(request))


@onboarding_router.put("/patient")
def patient_onboarding(body: PatientOnboardingIn, request: Request):
    user = current_user(request)
    if user["role"] != "patient":
        raise HTTPException(403, "Only patient accounts can use patient onboarding")
    with db.tx() as c:
        c.execute("INSERT INTO patient_profiles (user_id,name,affected_areas_json,goals_json,consent_local_analysis,completed_at) "
                  "VALUES (?,?,?,?,?,?) ON CONFLICT(user_id) DO UPDATE SET name=excluded.name, affected_areas_json=excluded.affected_areas_json, "
                  "goals_json=excluded.goals_json, consent_local_analysis=excluded.consent_local_analysis, completed_at=excluded.completed_at",
                  (user["id"], body.name, db.json.dumps(body.affected_areas), db.json.dumps(body.goals), int(body.consent_local_analysis), db.now()))
        c.execute("INSERT OR IGNORE INTO patients (id,name,condition,created_at) VALUES (?,?,?,?)",
                  (user["id"], body.name, ", ".join(body.affected_areas), db.now()))
    return _result(user)


@onboarding_router.put("/therapist")
def therapist_onboarding(body: TherapistOnboardingIn, request: Request):
    user = current_user(request)
    if user["role"] != "therapist":
        raise HTTPException(403, "Only therapist accounts can use therapist onboarding")
    with db.tx() as c:
        c.execute("INSERT INTO therapist_profiles (user_id,name,completed_at) VALUES (?,?,?) "
                  "ON CONFLICT(user_id) DO UPDATE SET name=excluded.name, completed_at=excluded.completed_at",
                  (user["id"], body.name, db.now()))
        c.execute("DELETE FROM therapist_specializations WHERE user_id=?", (user["id"],))
        c.execute("DELETE FROM therapist_exercises WHERE user_id=?", (user["id"],))
        c.executemany("INSERT INTO therapist_specializations (user_id,specialization) VALUES (?,?)",
                      [(user["id"], item) for item in body.specializations])
        c.executemany("INSERT INTO therapist_exercises (user_id,exercise) VALUES (?,?)",
                      [(user["id"], item) for item in body.supported_exercises])
    return _result(user)
