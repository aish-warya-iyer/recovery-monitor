"""Demo data (#52): two sample patients whose sessions are clips of public REHAB24-6 squat videos,
analysed by the real pipeline. Nothing here is a real patient.

    cd recovery-monitor-backend && ~/rm-venv/bin/python -m app.seed --reset

Needs the dataset on the Nano (~/rm-data/rehab24/videos, see model/README.md).
"""

import argparse
import shutil
from datetime import datetime, timedelta, timezone

import json

from app import db, jobs
from app.auth import hash_password, seed_demo_users
from app.config import DATA_DIR, REFERENCE_DIR, VIDEO_DIR
from app.video import clip

SAMPLE = "Public sample data: REHAB24-6 (CC BY-NC 4.0, Černek et al., SISAP 2024). Not a real patient."
EX6 = "Ex6/{vid}-Camera18-30fps-transposed.mp4"  # camera 18 = side view for these reps

PATIENTS = [
    {"id": "jordan", "name": "Jordan Mitchell", "condition": f"Knee rehab, week 6 (sample). {SAMPLE}"},
    {"id": "sam", "name": "Sam Rivera", "condition": f"Knee pain when squatting (sample). {SAMPLE}"},
]
REFERENCE = {"title": "Bodyweight squat, side view: 3 correct reps", "vid": "PM_043", "start": 10.5, "end": 22.0}

# (patient, video, start s, end s, days ago, pain, review decision or None, note)
# Order matters: an approved session becomes the baseline later sessions are compared with.
# Jordan = REHAB24-6 subject in PM_008, Sam = subject in PM_043 (each patient is one real person).
SESSIONS = [
    ("jordan", "PM_008", 3.0, 24.0, 9, 4, "approve", "Baseline session: good depth and control."),
    ("jordan", "PM_008", 46.5, 83.0, 5, 3, "approve", "Consistent reps. Pain trending down."),
    ("jordan", "PM_008", 93.5, 113.0, 0, 2, None, None),
    ("sam", "PM_043", 10.5, 32.0, 4, 3, "approve", "Baseline session: controlled squats."),
    ("sam", "PM_043", 47.0, 63.5, 0, 6, None, None),
]


def reset():
    shutil.rmtree(VIDEO_DIR, ignore_errors=True)
    shutil.rmtree(REFERENCE_DIR, ignore_errors=True)
    for p in DATA_DIR.glob("recovery_monitor.sqlite3*"):
        p.unlink()
    db._conn = None
    VIDEO_DIR.mkdir(parents=True, exist_ok=True)
    REFERENCE_DIR.mkdir(parents=True, exist_ok=True)


def main():
    from model.config import VIDEOS

    ap = argparse.ArgumentParser()
    ap.add_argument("--reset", action="store_true", help="delete all app data first")
    args = ap.parse_args()
    if args.reset:
        reset()
    now = datetime.now(timezone.utc)

    ref_dir = REFERENCE_DIR / "demo-squat-side"
    ref_dir.mkdir(parents=True, exist_ok=True)
    clip(VIDEOS / EX6.format(vid=REFERENCE["vid"]), ref_dir / "video.mp4", REFERENCE["start"], REFERENCE["end"])
    with db.tx() as c:
        ref_id = c.execute("INSERT INTO reference_videos (exercise, title, path, source, created_at) VALUES (?,?,?,?,?)",
                           ("squat", REFERENCE["title"], str(ref_dir / "video.mp4"), SAMPLE, db.now())).lastrowid
        for p in PATIENTS:
            c.execute("INSERT INTO patients (id, name, condition, created_at) VALUES (?,?,?,?)",
                      (p["id"], p["name"], p["condition"], (now - timedelta(days=14)).isoformat(timespec="seconds")))
            c.execute("INSERT INTO protocols (patient_id, version, exercise, target_reps, target_depth_deg, "
                      "pain_threshold, tempo, reference_video_id, notes, approved_by, created_at) "
                      "VALUES (?,1,'squat',10,100,5,'Slow and controlled, 2 s down',?,?, 'Physiotherapist', ?)",
                      (p["id"], ref_id, "Film from the side, whole body in frame.",
                       (now - timedelta(days=14)).isoformat(timespec="seconds")))

    for i, (pid, vid, start, end, days_ago, pain, decision, note) in enumerate(SESSIONS):
        sid = f"demo-{pid}-{i + 1}"
        folder = VIDEO_DIR / sid
        folder.mkdir(parents=True, exist_ok=True)
        raw = folder / "upload.mp4"
        clip(VIDEOS / EX6.format(vid=vid), raw, start, end)
        ts = (now - timedelta(days=days_ago, hours=2)).isoformat(timespec="seconds")
        protocol = db.one("SELECT id FROM protocols WHERE patient_id = ? ORDER BY version DESC LIMIT 1", pid)
        with db.tx() as c:
            c.execute("INSERT INTO sessions (id, patient_id, protocol_id, exercise, status, stage, progress, source, "
                      "created_at, updated_at) VALUES (?,?,?, 'squat', 'uploaded', 'queued', 0, 'demo', ?, ?)",
                      (sid, pid, protocol["id"], ts, ts))
        print(f"analysing {sid} ({end - start:.0f} s clip of {vid}) ...", flush=True)
        jobs.run(sid, raw)  # synchronous here
        s = db.one("SELECT status, result_json FROM sessions WHERE id = ?", sid)
        r = db.loads(s["result_json"]) or {}
        print(f"  {s['status']}: {r.get('repetitions')} reps, {r.get('correct_repetitions')} look correct", flush=True)
        with db.tx() as c:
            c.execute("INSERT INTO check_ins (session_id, pain_score, stiffness, comment, created_at) VALUES (?,?,?,?,?)",
                      (sid, pain, int(pain >= 5), "Knee felt sore on the way down." if pain >= 5 else "Felt fine.", ts))
            if decision:
                c.execute("INSERT INTO reviews (session_id, decision, notes, rep_labels_json, reference_video_id, "
                          "reviewer, created_at) VALUES (?,?,?, '{}', ?, 'Physiotherapist', ?)",
                          (sid, decision, note, ref_id, ts))
    seed_accounts()
    print("done:", db.one("SELECT COUNT(*) n FROM sessions")["n"], "sessions")


DEMO_PASSWORD = "recovery-demo"
# Sign-in accounts for the demo. A patient's user id equals their patient id, which links the login to the
# movement data. patient.demo@example.com (from seed_demo_users) stays fresh to show onboarding + intake.
ACCOUNTS = [
    ("jordan", "jordan@demo.local", "patient", "Jordan Mitchell", ["knee"]),
    ("sam", "sam@demo.local", "patient", "Sam Rivera", ["knee"]),
    ("test", "test@demo.local", "patient", "Test Patient", ["knee"]),
]


def seed_accounts():
    seed_demo_users()
    now = db.now()
    with db.tx() as c:
        c.execute("INSERT OR IGNORE INTO patients (id, name, condition, created_at) VALUES "
                  "('test', 'Test Patient', 'Real-video testing (our team, not a patient).', ?)", (now,))
        if not c.execute("SELECT 1 FROM protocols WHERE patient_id='test'").fetchone():
            c.execute("INSERT INTO protocols (patient_id, version, exercise, target_reps, target_depth_deg, pain_threshold, "
                      "tempo, notes, approved_by, created_at) VALUES ('test',1,'squat',10,100,5,'Slow and controlled',"
                      "'Film from the side, whole body in frame.','Physiotherapist',?)", (now,))
        for uid, email, role, name, areas in ACCOUNTS:
            c.execute("INSERT OR IGNORE INTO users (id,email,password_hash,role,created_at) VALUES (?,?,?,?,?)",
                      (uid, email, hash_password(DEMO_PASSWORD), role, now))
            c.execute("INSERT OR IGNORE INTO patient_profiles (user_id,name,affected_areas_json,goals_json,"
                      "consent_local_analysis,completed_at) VALUES (?,?,?,?,1,?)",
                      (uid, name, json.dumps(areas), json.dumps(["strength"]), now))
        c.execute("INSERT OR IGNORE INTO therapist_profiles (user_id,name,completed_at) VALUES "
                  "('demo-therapist','Demo Physiotherapist',?)", (now,))
        for spec in ("lower_body", "upper_body", "general_mobility"):
            c.execute("INSERT OR IGNORE INTO therapist_specializations (user_id,specialization) VALUES "
                      "('demo-therapist',?)", (spec,))
        for ex in ("squat", "leg_lunge", "leg_abduction", "arm_abduction", "arm_vw", "push_ups"):
            c.execute("INSERT OR IGNORE INTO therapist_exercises (user_id,exercise) VALUES ('demo-therapist',?)", (ex,))
    print("accounts: therapist.demo@example.com, jordan@demo.local, sam@demo.local, test@demo.local, "
          f"patient.demo@example.com (new) - password {DEMO_PASSWORD}")


if __name__ == "__main__":
    main()
