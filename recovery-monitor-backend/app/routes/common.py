"""Helpers shared by the route modules: building the session view the UI gets."""

from app import db
from app.flags import session_flag


def _protocol_dict(protocol_id):
    return db.one("SELECT * FROM protocols WHERE id = ?", protocol_id) if protocol_id else None


def _check_in(session_id):
    return db.one("SELECT * FROM check_ins WHERE session_id = ?", session_id)


def _previous_check_in(row):
    return db.one("SELECT c.* FROM check_ins c JOIN sessions s ON s.id = c.session_id "
                  "WHERE s.patient_id = ? AND s.created_at < ? ORDER BY s.created_at DESC LIMIT 1",
                  row["patient_id"], row["created_at"])


def latest_review(session_id):
    r = db.one("SELECT * FROM reviews WHERE session_id = ? ORDER BY id DESC LIMIT 1", session_id)
    if r:
        r["rep_labels"] = db.loads(r.pop("rep_labels_json")) or {}
    return r


def flag_for(row, result=None, check_in=None) -> dict:
    result = result if result is not None else db.loads(row["result_json"])
    check_in = check_in if check_in is not None else _check_in(row["id"])
    return session_flag(result, check_in, _previous_check_in(row), _protocol_dict(row["protocol_id"]))


def media_urls(row) -> dict:
    sid = row["id"]
    return {
        "video_url": f"/api/sessions/{sid}/video" if row["video_path"] else None,
        "annotated_video_url": f"/api/sessions/{sid}/annotated-video" if row["annotated_path"] else None,
        "thumbnail_url": f"/api/sessions/{sid}/thumbnail" if row["thumbnail_path"] else None,
    }


def session_summary(row) -> dict:
    """Compact per-session record for lists and trend charts."""
    result = db.loads(row["result_json"]) or {}
    check_in = _check_in(row["id"])
    review = latest_review(row["id"])
    metrics = result.get("metrics") or {}
    return {
        "id": row["id"], "patient_id": row["patient_id"], "exercise": row["exercise"], "created_at": row["created_at"],
        "status": row["status"], "stage": row["stage"], "progress": row["progress"], "error": row["error"],
        "repetitions": result.get("repetitions"), "correct_repetitions": result.get("correct_repetitions"),
        "form_score": result.get("form_score"), "median_depth_deg": metrics.get("median_depth_deg"),
        "reps_reaching_target": metrics.get("reps_reaching_target"),
        "pain_score": check_in["pain_score"] if check_in else None,
        "flag": flag_for(row, result, check_in) if row["result_json"] else None,
        "review": review and {"decision": review["decision"], "created_at": review["created_at"]},
        **media_urls(row),
    }


def session_detail(row) -> dict:
    result = db.loads(row["result_json"])
    check_in = _check_in(row["id"])
    return {
        "id": row["id"], "patient_id": row["patient_id"], "exercise": row["exercise"], "source": row["source"],
        "status": row["status"], "stage": row["stage"], "progress": row["progress"], "error": row["error"],
        "duration_s": row["duration_s"], "created_at": row["created_at"], "updated_at": row["updated_at"],
        "protocol": _protocol_dict(row["protocol_id"]),
        "result": result,
        "check_in": check_in,
        "flag": flag_for(row, result, check_in) if result else None,
        "review": latest_review(row["id"]),
        **media_urls(row),
    }
