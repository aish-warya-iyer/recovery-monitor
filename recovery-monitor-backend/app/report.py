"""AI draft report for the physiotherapist: movement evidence + what the patient said -> structured draft.

The local LLM (Ollama now, ZRT later; both on this device) only WRITES from facts it is given:
- red flags are decided by fixed rules here, never by the LLM, so they cannot be missed
- every number in the LLM's text must appear in the input facts, otherwise the text is rejected
- if the LLM is unavailable or keeps failing the checks, a plain template report is used
The report is a draft: the patient only sees its message after the physiotherapist approves.
"""

import json
import re
import time

import httpx

from app import db
from app.config import LLM_MODEL, LLM_URL

RED_FLAG_WORDS = [
    "numb", "tingl", "pins and needles", "swell", "swollen", "fell", "fall ", "gave way", "giving way",
    "can't put weight", "cannot put weight", "can't bear weight", "sharp pain", "stabbing", "pop", "locked",
    "locking", "dizzy", "faint", "chest pain", "short of breath", "fever", "bruis", "unbearable",
]

SCHEMA = {
    "type": "object",
    "properties": {
        "patient_said": {"type": "string", "maxLength": 400},
        "movement_summary": {"type": "string", "maxLength": 700},
        "agreement": {"type": "string", "enum": ["consistent", "partly_consistent", "inconsistent", "not_enough_info"]},
        "agreement_note": {"type": "string", "maxLength": 600},
        "concerns": {"type": "array", "items": {"type": "string", "maxLength": 200}, "maxItems": 4},
        "questions_for_patient": {"type": "array", "items": {"type": "string", "maxLength": 160}, "maxItems": 3},
        "coaching_cues": {"type": "array", "items": {"type": "string", "maxLength": 160}, "maxItems": 3},
        "suggested_next_step": {"type": "string", "minLength": 30, "maxLength": 300},
        "patient_message": {"type": "string", "minLength": 40, "maxLength": 500},
    },
    "required": ["patient_said", "movement_summary", "agreement", "agreement_note", "concerns",
                 "questions_for_patient", "coaching_cues", "suggested_next_step", "patient_message"],
}

SYSTEM = """You help a physiotherapist review a patient's home exercise session.
You receive FACTS as JSON: measured movement results from the video analysis, what the patient said (voice
transcript and/or typed text), their pain score, their plan and recent history.

Rules:
- Use ONLY the facts. Never invent measurements, numbers, symptoms or history.
- Every number you write must appear in the facts. If unsure, leave the number out.
- Do not diagnose, do not name medical conditions, do not prescribe. You suggest; the physiotherapist decides.
- patient_said: the patient's own words from check_in (transcript and comment), summarised faithfully. If check_in
  is null or has no words, write exactly: "The patient has not added a comment yet."
- movement.exercise_actually_done is what the video shows. Describe THAT exercise (never call it the plan's
  exercise if they differ). If it differs from plan.exercise, say so clearly. Coaching cues must be about the
  exercise actually done.
- movement_summary: what the video measured, in plain words for a clinician.
- agreement: compare what the patient said with what the video showed; explain briefly in agreement_note.
- concerns: the most important points for the physiotherapist, most important first.
- questions_for_patient: 1-3 short follow-up questions the physiotherapist could ask (e.g. about when the pain
  started or what makes it worse).
- coaching_cues: short, concrete movement cues based on the flagged reasons.
- suggested_next_step: ONE sentence, written for the physiotherapist, proposing what they might do next and why.
  It is only a draft.
- patient_message: written on behalf of the care team, warm and simple, 2-3 sentences. Thank the patient,
  mention one thing to focus on, and say their physiotherapist will review the session. Do NOT promise calls,
  appointments or plan changes, and do not include angles or technical terms.
- Write in plain English, short sentences."""


def red_flags(facts: dict) -> list[str]:
    flags = []
    ci = facts.get("check_in") or {}
    pain = ci.get("pain_score")
    if pain is not None and pain >= 8:
        flags.append(f"Severe pain reported ({pain}/10)")
    prev = facts.get("previous_pain")
    if pain is not None and prev is not None and pain - prev >= 2:
        flags.append(f"Pain rose from {prev} to {pain} since the last session")
    words = " ".join(filter(None, [ci.get("transcript"), ci.get("comment")])).lower()
    hits = sorted({w.strip() for w in RED_FLAG_WORDS if w in words})
    if hits:
        flags.append("Patient mentioned: " + ", ".join(hits))
    mv = facts.get("movement") or {}
    if mv.get("wrong_exercise"):
        flags.append(mv["wrong_exercise"])
    if mv.get("status") == "rejected_quality":
        flags.append("Video could not be analysed reliably")
    return flags


def build_facts(session: dict) -> dict:
    r = db.loads(session["result_json"]) or {}
    ci = db.one("SELECT pain_score, stiffness, comment, transcript FROM check_ins WHERE session_id = ?", session["id"])
    proto = db.one("SELECT * FROM protocols WHERE id = ?", session["protocol_id"]) if session["protocol_id"] else None
    patient = db.one("SELECT name, condition FROM patients WHERE id = ?", session["patient_id"])
    hist = []
    prev_pain = None
    for h in db.all_("SELECT s.id, s.created_at, s.result_json, c.pain_score FROM sessions s LEFT JOIN check_ins c "
                     "ON c.session_id = s.id WHERE s.patient_id = ? AND s.created_at < ? AND s.result_json IS NOT NULL "
                     "ORDER BY s.created_at DESC LIMIT 3", session["patient_id"], session["created_at"]):
        hr = db.loads(h["result_json"]) or {}
        hist.append({"date": h["created_at"][:10], "reps": hr.get("repetitions"),
                     "reps_flagged": sum(not x.get("predicted_correct", True) for x in hr.get("reps", [])),
                     "pain": h["pain_score"]})
        if prev_pain is None and h["pain_score"] is not None:
            prev_pain = h["pain_score"]
    reps = r.get("reps", [])
    flagged = [{"rep": x["index"], "value_deg": x.get("peak_deg"),
                "reasons": [f["message"] for f in x.get("flag_reasons", [])][:2]}
               for x in reps if not x.get("predicted_correct", True)][:6]
    vlm = r.get("vlm") or {}
    wrong = None
    if vlm.get("mismatch"):
        wrong = (f"Video looks like {r.get('exercise_label', vlm.get('detected_exercise'))} but the plan is "
                 f"{(vlm.get('planned_exercise') or '').replace('_', ' ')}")
    return {
        "patient": {"first_name": (patient or {}).get("name", "").split(" ")[0], "condition": (patient or {}).get("condition")},
        "plan": proto and {"exercise": proto["exercise"].replace("_", " "), "target_reps": proto["target_reps"],
                           "pain_alert_at": proto["pain_threshold"], "notes": proto["notes"]},
        "movement": {
            "exercise_actually_done": r.get("exercise_label") or r.get("exercise"), "status": r.get("status"),
            "measure": r.get("measure_label") or (r.get("angle_series") or {}).get("label"),
            "reps_done": r.get("repetitions"), "reps_flagged": len([x for x in reps if not x.get("predicted_correct", True)]),
            "flagged_reps": flagged, "camera_view": (r.get("quality") or {}).get("view"),
            "video_quality_issues": (r.get("quality") or {}).get("instructions", []),
            "session_flags": (r.get("flag") or {}).get("reasons", []), "wrong_exercise": wrong,
            "compared_with_personal_baseline": bool((r.get("model") or {}).get("classifier")),
        },
        "check_in": ci and {"pain_score": ci["pain_score"], "stiffness": bool(ci["stiffness"]) if ci["stiffness"] is not None else None,
                            "comment": ci["comment"] or None, "transcript": ci["transcript"] or None},
        "previous_pain": prev_pain,
        "history": hist,
    }


def _numbers(text: str) -> set[str]:
    return {n.rstrip(".").lstrip("0") or "0" for n in re.findall(r"\d+(?:\.\d+)?", text)}


def check_numbers(draft: dict, facts: dict) -> list[str]:
    allowed = _numbers(json.dumps(facts)) | {str(i) for i in range(0, 11)}
    texts = [draft.get(k, "") for k in ("patient_said", "movement_summary", "agreement_note",
                                        "suggested_next_step", "patient_message")]
    texts += draft.get("concerns", []) + draft.get("questions_for_patient", []) + draft.get("coaching_cues", [])
    bad = set()
    for t in texts:
        bad |= {n for n in _numbers(t) if n not in allowed and n.split(".")[0] not in allowed}
    return sorted(bad)


NO_COMMENT = "The patient has not added a comment yet."


def enforce(draft: dict, facts: dict) -> dict:
    """Facts the LLM must not get wrong are set by code, whatever it wrote."""
    ci = facts.get("check_in") or {}
    words = [w.strip() for w in (ci.get("transcript"), ci.get("comment")) if w and w.strip()]
    if words:
        # The patient's own words, verbatim: never a paraphrase the physio has to trust.
        draft["patient_said"] = " / ".join(f"“{w}”" for w in words)[:600]
    else:
        draft["patient_said"] = NO_COMMENT
        draft["agreement"] = "not_enough_info"
        draft["agreement_note"] = "Nothing to compare yet: the patient has not described how the session felt."
        draft["questions_for_patient"] = draft.get("questions_for_patient") or [
            "How did the exercise feel today?", "Did you have any pain during or after the session?"]
    return draft


def template(facts: dict) -> dict:
    mv, ci = facts["movement"], facts.get("check_in") or {}
    said = ci.get("transcript") or ci.get("comment") or NO_COMMENT
    return {
        "patient_said": said[:400],
        "movement_summary": f"{mv['reps_done'] or 0} {str(mv['exercise_actually_done']).lower()} reps; {mv['reps_flagged']} flagged for review.",
        "agreement": "not_enough_info", "agreement_note": "Automatic summary; please review the video and reps.",
        "concerns": mv["session_flags"][:4], "questions_for_patient": [], "coaching_cues": [],
        "suggested_next_step": "Review the flagged reps and the patient's comments.",
        "patient_message": "Thanks for recording your session. Your physiotherapist will review it soon.",
    }


def generate(session_id: str) -> dict:
    s = db.one("SELECT * FROM sessions WHERE id = ?", session_id)
    if not s or not s["result_json"]:
        raise ValueError("session not analysed yet")
    facts = build_facts(s)
    flags = red_flags(facts)
    t0 = time.time()
    draft, source, problems = None, "template", []
    note = ""
    for attempt in range(2):
        try:
            r = httpx.post(f"{LLM_URL}/api/chat", timeout=180, json={
                "model": LLM_MODEL, "stream": False, "think": False, "format": SCHEMA, "keep_alive": "2h",
                "options": {"temperature": 0.2, "num_ctx": 16384},
                "messages": [{"role": "system", "content": SYSTEM},
                             {"role": "user", "content": "FACTS:\n" + json.dumps(facts, indent=1) + note}]})
            r.raise_for_status()
            cand = json.loads(r.json()["message"]["content"])
        except Exception as e:  # noqa: BLE001
            problems.append(f"LLM call failed: {e}"[:200])
            break
        bad = check_numbers(cand, facts)
        if not bad:
            draft, source = cand, "llm"
            break
        problems.append(f"attempt {attempt + 1}: numbers not in the facts: {', '.join(bad)}")
        note = f"\n\nYour previous answer used numbers that are not in the facts ({', '.join(bad)}). Remove them."
    if draft is None:
        draft = template(facts)
    draft = enforce(draft, facts)
    report = {**draft, "red_flags": flags, "urgent": bool(flags), "source": source, "model": LLM_MODEL if source == "llm" else None,
              "checks": {"numbers_verified": source == "llm", "problems": problems},
              "seconds": round(time.time() - t0, 1), "status": "draft_needs_physio_approval"}
    with db.tx() as c:
        c.execute("INSERT INTO reports (session_id, report_json, created_at) VALUES (?,?,?) ON CONFLICT(session_id) "
                  "DO UPDATE SET report_json = excluded.report_json, created_at = excluded.created_at",
                  (session_id, json.dumps(report), db.now()))
    return report


def get(session_id: str) -> dict | None:
    r = db.one("SELECT report_json, created_at FROM reports WHERE session_id = ?", session_id)
    return {**json.loads(r["report_json"]), "created_at": r["created_at"]} if r else None
