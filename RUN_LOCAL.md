# Run Recovery Monitor locally

Open two terminal windows from the project workspace.

## Terminal 1: backend

```bash
cd recovery-monitor-backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Check that it is ready:

```bash
curl http://127.0.0.1:8000/api/health
```

## Terminal 2: frontend

```bash
cd recovery-monitor-frontend
npm install
npm run dev
```

Open the Vite URL, usually `http://localhost:5173`.

Click **Start analysis**. The frontend sends a POST request to the local FastAPI endpoint and updates the movement evidence card with the returned structured result.

The current backend response is a deterministic local demo stub. The next implementation replaces that stub with MediaPipe, NumPy features, the repetition counter, and XGBoost.
