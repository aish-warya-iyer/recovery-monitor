"""Local authentication helpers."""

import hashlib
import hmac
import secrets
from datetime import datetime, timezone

from fastapi import HTTPException, Request

from app import db

SESSION_COOKIE = "rm_session"


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, 240_000)
    return f"pbkdf2_sha256$240000${salt.hex()}${digest.hex()}"


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, rounds, salt, expected = encoded.split("$", 3)
        actual = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), int(rounds))
        return algorithm == "pbkdf2_sha256" and hmac.compare_digest(actual.hex(), expected)
    except (ValueError, TypeError):
        return False


def public_user(user: dict) -> dict:
    return {"id": user["id"], "email": user["email"], "role": user["role"]}


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def create_session(user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    with db.tx() as c:
        c.execute("INSERT INTO auth_sessions (token_hash, user_id, expires_at, created_at) VALUES (?,?,datetime('now','+30 days'),?)",
                  (token_hash, user_id, _now()))
    return token


def current_user(request: Request) -> dict:
    token = request.cookies.get(SESSION_COOKIE)
    if not token:
        raise HTTPException(401, "Authentication required")
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    user = db.one("SELECT u.* FROM users u JOIN auth_sessions s ON s.user_id=u.id "
                  "WHERE s.token_hash=? AND s.expires_at > datetime('now')", token_hash)
    if not user:
        raise HTTPException(401, "Session expired or invalid")
    return user


def drop_session(request: Request) -> None:
    token = request.cookies.get(SESSION_COOKIE)
    if token:
        token_hash = hashlib.sha256(token.encode()).hexdigest()
        with db.tx() as c:
            c.execute("DELETE FROM auth_sessions WHERE token_hash=?", (token_hash,))

def seed_demo_users() -> None:
    users = (("demo-patient", "patient.demo@example.com", "patient"),
             ("demo-therapist", "therapist.demo@example.com", "therapist"))
    for user_id, email, role in users:
        if db.one("SELECT id FROM users WHERE email=?", email):
            continue
        with db.tx() as c:
            c.execute("INSERT INTO users (id,email,password_hash,role,created_at) VALUES (?,?,?,?,?)",
                      (user_id, email, hash_password("recovery-demo"), role, db.now()))
