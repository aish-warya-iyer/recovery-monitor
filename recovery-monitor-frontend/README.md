# Recovery Monitor Frontend

This is the first React/Vite workflow prototype for NanoForge Recovery Monitor.
It uses simulated data so we can see the complete user experience before connecting FastAPI, MediaPipe, REHAB24-6, Whisper, XGBoost, and SQLite.

## Run locally

```bash
npm install
npm run dev
```

Open the local URL printed by Vite.

For the Start analysis button to return a result, run the backend in a second terminal:

```bash
cd ../recovery-monitor-backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Then keep the frontend running at `http://localhost:5173`. The browser calls only `http://127.0.0.1:8000`; no cloud service is used.

## Current workflow components

- Local runtime and privacy status
- Workspace navigation
- Session setup and patient context
- Exercise video/camera panel
- Pose-tracking state
- Movement evidence card
- Repetition, form, range-of-motion, and smoothness metrics
- Recovery trajectory chart
- Patient voice check-in and pain correction
- Therapist approval workflow
- Uncertainty and non-diagnostic disclaimer

## Next connections

1. Replace mock analysis with a FastAPI endpoint.
2. Connect MediaPipe pose landmarks and the repetition counter.
3. Load REHAB24-6 evaluation results.
4. Add SQLite session persistence.
5. Add local Whisper transcription.
