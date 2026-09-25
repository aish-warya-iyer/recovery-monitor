"""API flow with the model replaced by the real fixture output (no dataset or GPU needed)."""

import json
import shutil
import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

FIXTURE = json.loads((Path(__file__).resolve().parents[2] / "fixtures" / "analysis_result.json").read_text())


@pytest.fixture()
def client(monkeypatch):
    import model.analyze

    def fake_analyze(path, exercise, protocol, annotated_path=None, progress=None, baseline=None):
        if progress:
            progress("pose", 0.5)
        if annotated_path:
            shutil.copy(path, annotated_path)
        r = json.loads(json.dumps(FIXTURE))
        r.update(protocol=protocol, baseline_seen=len(baseline or []))
        return r

    monkeypatch.setattr(model.analyze, "analyze_video", fake_analyze)
    from app.main import app

    with TestClient(app) as c:
        yield c


def wait_done(client, sid, timeout=30):
    t0 = time.time()
    while time.time() - t0 < timeout:
        s = client.get(f"/api/sessions/{sid}").json()
        if s["stage"] in ("done", "failed"):
            return s
        time.sleep(0.2)
    raise AssertionError("analysis did not finish")


def test_health_reports_local(client):
    h = client.get("/api/health").json()
    assert h["inference_local"] is True and h["cloud_ai_disabled"] is True


def test_full_patient_physio_flow(client, tiny_video):
    p = client.post("/api/patients", json={"name": "Test Patient", "id": "t-flow"}).json()
    proto = client.post(f"/api/patients/{p['id']}/protocol",
                        json={"target_reps": 10, "target_depth_deg": 95, "pain_threshold": 5}).json()
    assert proto["version"] == 1

    with tiny_video.open("rb") as f:
        up = client.post(f"/api/patients/{p['id']}/sessions", files={"video": ("clip.mp4", f, "video/mp4")})
    assert up.status_code == 202
    sid = up.json()["session_id"]
    s = wait_done(client, sid)
    assert s["status"] == FIXTURE["status"] and s["result"]["protocol"]["target_depth_deg"] == 95
    assert client.get(f"/api/sessions/{sid}/video").status_code == 200
    assert client.get(f"/api/sessions/{sid}/annotated-video", headers={"Range": "bytes=0-99"}).status_code == 206

    s = client.post(f"/api/patients/{p['id']}/sessions/{sid}/check-in", json={"pain_score": 7}).json()
    assert s["flag"]["severity"] == "urgent"
    queue = client.get("/api/review-queue").json()
    assert queue[0]["id"] == sid

    # safety gate: can't approve high pain without acknowledging it
    r = client.post(f"/api/sessions/{sid}/review", json={"decision": "approve"})
    assert r.status_code == 409
    r = client.post(f"/api/sessions/{sid}/review", json={"decision": "approve", "acknowledge_pain": True,
                                                        "rep_labels": {"1": "incorrect"}})
    assert r.status_code == 201 and r.json()["review"]["rep_labels"] == {"1": "incorrect"}
    assert all(x["id"] != sid for x in client.get("/api/review-queue").json())

    history = client.get(f"/api/patients/{p['id']}/sessions").json()
    assert history[0]["pain_score"] == 7 and history[0]["review"]["decision"] == "approve"

    # the approved session becomes the baseline for the next one
    with tiny_video.open("rb") as f:
        sid2 = client.post(f"/api/patients/{p['id']}/sessions", files={"video": ("c2.mp4", f, "video/mp4")}).json()["session_id"]
    assert wait_done(client, sid2)["result"]["baseline_seen"] > 0

    assert client.delete(f"/api/sessions/{sid2}").status_code == 204
    assert client.get(f"/api/sessions/{sid2}").status_code == 404


def test_rejects_non_video(client, tmp_path):
    client.post("/api/patients", json={"name": "X", "id": "t-bad"})
    bad = tmp_path / "notes.txt"
    bad.write_text("hello")
    r = client.post("/api/patients/t-bad/sessions", files={"video": ("notes.txt", bad.open("rb"), "text/plain")})
    assert r.status_code == 415


def test_legacy_check_in_no_longer_crashes(client):
    r = client.post("/api/sessions/legacy-1/check-in", json={"pain_score": 6, "comment": "sore"})
    assert r.status_code == 200
    r = client.post("/api/sessions/legacy-1/decision", json={"decision": "approve"})
    assert r.status_code == 409  # gate moved to the decision endpoint


def test_eval_summary_has_measured_numbers(client):
    e = client.get("/api/eval/summary").json()
    assert e["angle_accuracy"]["per_frame"]["side"]["mae_deg"] < 10


def test_authenticated_patient_therapist_intake_flow(client):
    patient = client.post("/api/auth/signup", json={
        "email": "workflow-patient@example.com",
        "password": "development-password",
        "role": "patient",
    })
    assert patient.status_code == 201
    patient_user = patient.json()["user"]

    onboard = client.put("/api/onboarding/patient", json={
        "name": "Workflow Patient",
        "affected_areas": ["knee"],
        "goals": ["improve_strength"],
        "consent_local_analysis": True,
    })
    assert onboard.status_code == 200

    intake = client.post("/api/patient/intakes", json={
        "affected_areas": ["knee"],
        "issue_types": ["pain_during_movement"],
        "when_it_happens": ["during_movement"],
        "pain_score": 3,
        "duration": "one_to_three_months",
        "trend": "unchanged",
        "limitations": [],
        "goals": ["improve_strength"],
        "notes": "Squats feel difficult after a long day.",
    })
    assert intake.status_code == 201
    intake_id = intake.json()["id"]

    client.cookies.clear()
    mismatch = client.post("/api/auth/signup", json={
        "email": "workflow-upper@example.com",
        "password": "development-password",
        "role": "therapist",
    })
    assert mismatch.status_code == 201
    assert client.put("/api/onboarding/therapist", json={
        "name": "Upper Body Therapist",
        "specializations": ["upper_body"],
        "supported_exercises": ["push_ups"],
    }).status_code == 200
    assert client.get("/api/therapist/intakes").json() == []

    client.cookies.clear()
    therapist = client.post("/api/auth/signup", json={
        "email": "workflow-therapist@example.com",
        "password": "development-password",
        "role": "therapist",
    })
    assert therapist.status_code == 201
    therapist_user = therapist.json()["user"]
    assert client.put("/api/onboarding/therapist", json={
        "name": "Workflow Therapist",
        "specializations": ["lower_body"],
        "supported_exercises": ["squat"],
    }).status_code == 200

    requests = client.get("/api/therapist/intakes").json()
    assert any(item["id"] == intake_id for item in requests)
    accepted = client.post(f"/api/therapist/intakes/{intake_id}/claim")
    assert accepted.status_code == 200
    assert accepted.json()["assigned_therapist_id"] == therapist_user["id"]

    plan = client.post(f"/api/therapist/intakes/{intake_id}/plan", json={
        "exercise": "squat",
        "target_reps": 8,
        "target_sets": 2,
        "target_depth_deg": 95,
        "pain_threshold": 5,
        "instructions": "Use a side view and stop if pain increases.",
    })
    assert plan.status_code == 201
    plan_id = plan.json()["id"]
    assert client.post(f"/api/therapist/plans/{plan_id}/approve", json={"notes": "Approved for testing."}).status_code == 200

    client.cookies.clear()
    assert client.post("/api/auth/login", json={
        "email": "workflow-patient@example.com",
        "password": "development-password",
    }).status_code == 200
    care_team = client.get("/api/patient/care-team")
    assert care_team.status_code == 200
    assert care_team.json()["therapist"] == {
        "id": therapist_user["id"],
        "email": "workflow-therapist@example.com",
        "name": "Workflow Therapist",
    }
    assert client.get("/api/patient/intakes").json()[0]["status"] == "approved"
