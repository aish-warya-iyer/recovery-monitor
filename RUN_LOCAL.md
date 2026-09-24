# Run Recovery Monitor Locally

Open two terminal windows from the project workspace.

## Terminal 1: Backend

Use the Python 3.11 environment because MediaPipe works reliably there on macOS.

```bash
conda activate recovery-monitor-py311

cd recovery-monitor-backend

pip install -r requirements.txt

python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

Check that the backend is ready:

```bash
curl http://127.0.0.1:8000/api/health
```

You should see a response similar to:

```json
{
  "status": "ready",
  "inference_local": true,
  "network_required": false,
  "cloud_ai_disabled": true
}
```

Keep this terminal running.

## Terminal 2: Frontend

Open a second terminal:

```bash
cd recovery-monitor-frontend

npm install

npm run dev
```

Open the Vite URL shown in the terminal. It is usually:

```text
http://localhost:5173
```

## Test the Application

1. Open the frontend in your browser.
2. Click `Choose exercise video`.
3. Select a video of a seated leg extension.
4. Confirm that the video preview appears.
5. Click `Start analysis`.
6. Wait for the analysis to finish.
7. Review:
   - Form quality
   - Repetitions
   - Correct form
   - Range of motion
   - Movement smoothness
   - Confidence
8. Edit the patient comment.
9. Select the patient-reported pain score.
10. Click `Save check-in`.
11. Click `Approve protocol` or `Request changes`.

## What the Backend Does

The current backend performs local movement analysis using:

- OpenCV for reading video frames
- MediaPipe Pose for body landmarks
- Knee-angle geometry
- Rule-based repetition counting
- Range-of-motion calculation
- Movement smoothness estimation
- Pose confidence calculation

The uploaded video is processed locally and is not sent to cloud AI.

## Demo Mode

If no video is uploaded, the application uses deterministic demo data.

If a video is uploaded, the backend runs the local MediaPipe analysis.

## Troubleshooting

### Backend unavailable

Make sure Terminal 1 is running:

```bash
python -m uvicorn main:app --reload --host 127.0.0.1 --port 8000
```

### MediaPipe import or compatibility errors

Make sure the Python 3.11 environment is active:

```bash
conda activate recovery-monitor-py311
python --version
```

The version should start with:

```text
Python 3.11
```

### Frontend cannot connect to backend

Confirm that:

- The backend is running on port `8000`.
- The frontend is running on port `5173`.
- You opened the correct Vite URL.
- The browser console does not show a CORS error.

### Stop the servers

Press:

```text
Ctrl + C
```

in each terminal window.