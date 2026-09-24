"""Health, evaluation numbers and the reference video library (#21, #29, #16)."""

import asyncio
import json
import shutil
import uuid

from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from app import db
from app.config import AI_ENDPOINTS, DEVICE_NAME, MODEL_RESULTS, REFERENCE_DIR
from app.guards import is_local, network_reachable
from app.video import VideoError, normalize

router = APIRouter(prefix="/api", tags=["system"])


@router.get("/health")
async def health():
    return {
        "status": "ready",
        "device": DEVICE_NAME,
        "inference_local": all(is_local(u) for u in AI_ENDPOINTS),  # also enforced at startup
        "cloud_ai_disabled": True,
        "network_required": False,
        "network_reachable": await asyncio.to_thread(network_reachable),
        "models": {"pose": "MediaPipe Pose Landmarker (full), on-device CPU",
                   "classifier": "XGBoost squat rep classifier (model/artifacts/squat_xgb.json)"},
    }


@router.get("/eval/summary")
def eval_summary():
    """Measured model numbers for the Evaluation page (#29). Anything not measured is null."""
    def load(name):
        p = MODEL_RESULTS / name
        return json.loads(p.read_text()) if p.exists() else None

    angles, reps, clf = load("angle_accuracy_squat.json"), load("rep_counting_squat.json"), load("classifier_squat.json")
    return {
        "dataset": "REHAB24-6 squats (Ex6): 9 subjects, 390 annotated reps; CC BY-NC 4.0 (Černek et al., SISAP 2024)",
        "angle_accuracy": angles and {"per_frame": angles["per_frame_error"]["image_2d"],
                                      "rep_depth": angles["rep_depth_error"]["image_2d"],
                                      "ground_truth": angles["ground_truth"], "example_rep": angles.get("example_rep")},
        "rep_counting": reps and {"overall": reps["summary"]["all"], "recall_by_view": reps["recall_by_view"]},
        "classifier": clf and {k: clf[k] for k in ("evaluation", "threshold", "n_reps", "n_incorrect", "n_subjects",
                                                   "xgboost", "rules_baseline", "xgboost_by_view")},
        "caveats": [
            "Healthy volunteers acting out mistakes, not patients; not clinical validation.",
            "Rep-counter settings and the classifier's feature set were chosen while looking at this data.",
            "Angles are only accurate from a side view.",
        ],
    }


@router.get("/reference-videos")
def list_reference_videos(exercise: str | None = None):
    rows = db.all_("SELECT * FROM reference_videos WHERE (? IS NULL OR exercise = ?) ORDER BY id", exercise, exercise)
    return [{**r, "url": f"/api/reference-videos/{r['id']}/video", "path": None} for r in rows]


@router.get("/reference-videos/{video_id}/video")
def reference_video(video_id: int):
    r = db.one("SELECT * FROM reference_videos WHERE id = ?", video_id)
    if not r:
        raise HTTPException(404, "No such reference video")
    return FileResponse(r["path"], media_type="video/mp4")


@router.post("/reference-videos", status_code=201)
async def add_reference_video(video: UploadFile = File(...), title: str = Form(...), exercise: str = Form("squat"),
                              source: str = Form("recorded by the physiotherapist")):
    from app.routes.sessions import save_upload

    folder = REFERENCE_DIR / uuid.uuid4().hex[:12]
    raw = await save_upload(video, folder)
    try:
        await asyncio.to_thread(normalize, raw, folder / "video.mp4")
    except VideoError as e:
        shutil.rmtree(folder, ignore_errors=True)
        raise HTTPException(422, str(e)) from e
    raw.unlink(missing_ok=True)
    with db.tx() as c:
        cur = c.execute("INSERT INTO reference_videos (exercise, title, path, source, created_at) VALUES (?,?,?,?,?)",
                        (exercise, title, str(folder / "video.mp4"), source, db.now()))
    return {"id": cur.lastrowid, "title": title, "url": f"/api/reference-videos/{cur.lastrowid}/video"}
