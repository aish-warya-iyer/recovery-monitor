# Recovery Monitor backend (FastAPI, local only)

Everything runs on the ZGX Nano: video conversion (bundled ffmpeg), pose estimation (MediaPipe),
rep analysis and the XGBoost classifier (`../model`), SQLite storage. No cloud AI; the app refuses to
start if an AI endpoint is configured off the device.

## Run

```bash
python3 -m venv ~/rm-venv && ~/rm-venv/bin/pip install -r requirements.txt
~/rm-venv/bin/python -m app.seed --reset     # optional: demo patients from public REHAB24-6 clips (needs ~/rm-data)
~/rm-venv/bin/uvicorn main:app --host 127.0.0.1 --port 8000
~/rm-venv/bin/python -m pytest tests         # API flow tests, no dataset or GPU needed
```

Data (SQLite, videos) goes to `data/` (gitignored); override with `RM_APP_DATA`.

## API

The analysis result format is in [`../docs/API_CONTRACT.md`](../docs/API_CONTRACT.md); a real example is
[`../fixtures/analysis_result.json`](../fixtures/analysis_result.json).

| | endpoint | |
|---|---|---|
| **system** | `GET /api/health` | device, `inference_local`, `network_reachable` (for the offline badge) |
| | `GET /api/eval/summary` | measured accuracy numbers for the Evaluation page |
| **patients** | `GET /api/patients` · `POST /api/patients` | list with current protocol and sessions awaiting review · create |
| | `GET /api/patients/{id}` | patient + current protocol |
| | `GET/POST /api/patients/{id}/protocol` · `GET .../protocol/history` | current plan · new version · history |
| | `GET /api/patients/{id}/sessions` | history for the trend chart (reps, depth, pain, flag, review) |
| **sessions** | `POST /api/patients/{id}/sessions` (multipart `video`) | upload → `202 {session_id}`; analysis runs in the background |
| | `GET /api/sessions/{id}/events` | Server-Sent Events: `progress` (stage, 0–1), then `done` / `failed` |
| | `GET /api/sessions/{id}` | status, result, check-in, flag, review, media URLs |
| | `GET /api/sessions/{id}/video` · `/annotated-video` · `/thumbnail` | H.264 MP4 with range requests (seeking works) |
| | `POST /api/patients/{pid}/sessions/{id}/check-in` | `{pain_score, stiffness, comment, transcript}` |
| | `DELETE /api/sessions/{id}` | removes video, results, check-in, reviews |
| **physio** | `GET /api/review-queue` | flagged, unreviewed sessions; urgent first, then oldest |
| | `POST /api/sessions/{id}/review` | `{decision, notes, rep_labels: {"3": "incorrect"}, reference_video_id, acknowledge_pain}` |
| | `GET /api/rep-corrections` | where the physio disagreed with the model (future training data) |
| **library** | `GET/POST /api/reference-videos` · `GET .../{id}/video` | physio-approved reference clips |
| **legacy** | `POST /api/analyze-session`, `/api/sessions/{id}/check-in`, `/decision` | what the current single-page UI calls |

## Rules worth knowing
- **Baseline:** once the physio approves a session, its reps become that patient's baseline; later sessions
  are judged by the classifier against it. Before that, rules only (the result says so).
- **Flags** (`app/flags.py`): any rep flagged, low tracking confidence, pain ≥ plan threshold (urgent),
  pain up since last session, fewer reps than the plan.
- **Safety gate:** approving a session whose pain is at/above the threshold needs `acknowledge_pain: true`.
- A restart marks interrupted analyses as failed so nothing looks "processing" forever.
