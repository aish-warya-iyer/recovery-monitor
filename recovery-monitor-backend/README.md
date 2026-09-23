# Recovery Monitor local backend

This FastAPI service is the first local control-plane connection for the React frontend.
The analysis endpoint is currently a deterministic local stub. It intentionally returns the same structured contract that the real MediaPipe, repetition-counter, and XGBoost pipeline will later produce.

## Run

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

## Endpoints

- `GET /api/health`
- `POST /api/analyze-session`

The endpoint is local-only and has no cloud AI dependency.
