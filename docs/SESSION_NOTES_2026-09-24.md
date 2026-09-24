# Recovery Monitor — Session Notes

**Date:** 2026-09-24  
**Branch:** `storyboard/landing-page`  
**Current commit before these notes:** `789c178`  
**Purpose:** Record the product, frontend, deployment, and design work completed during this session.

## 1. Branch and repository workflow

- Worked on the `storyboard/landing-page` branch.
- The branch was pushed to the configured `origin` remote, which points to Arya's fork:
  `https://github.com/aryaMehta26/recovery-monitor.git`
- The upstream repository is configured separately as `upstream`:
  `https://github.com/aish-warya-iyer/recovery-monitor.git`
- The branch needs to be pushed to upstream as well if the team is checking branches in the upstream repository.
- No dataset files were staged or committed.

## 2. Landing page and visual product direction

The landing page was redesigned to communicate the product to patients, physiotherapists, and potential investors.

Main product message:

> Recovery Monitor turns everyday rehabilitation videos into structured movement evidence while keeping analysis on the local device.

The page now includes:

- Clear patient and physiotherapist entry points.
- Product messaging focused on the space between appointments.
- A three-step product loop: record movement, see evidence, stay connected.
- Privacy and local-analysis messaging.
- Accuracy and privacy navigation.
- Exercise-library visual content covering more than knee rehabilitation.
- A larger live movement sample area.
- Animated 3D-style rehabilitation visuals for repeated exercise movement.
- Apple/Hyrzilla-inspired typography, whitespace, muted gradients, cards, hover states, and responsive layouts.

Generated local visual assets were added to:

- `recovery-monitor-frontend/src/assets/rehab-motion-person.png`
- `recovery-monitor-frontend/src/assets/rehab-motion-person-standing.png`
- `recovery-monitor-frontend/src/assets/exercise-library-strip.png`

These are frontend presentation assets only and are not model or patient data.

## 3. Patient dashboard work

The patient area remains accessible through routes such as:

- `#/patient/jordan`
- `#/patient/sam`

The patient dashboard was expanded without removing the existing analysis workflow.

Added or improved:

- Recovery-status pill.
- Next-step card.
- Completed-session summary.
- Care-team and privacy context.
- Patient-friendly guidance callout.
- Smooth scroll from “Record a session” to the recording area.
- A three-step patient workflow: follow plan, record movement, check in.
- Responsive mobile layout.
- Hover states and reduced-motion support.
- Clear protocol information, including exercise, repetitions, target depth, tempo, notes, and reference video.

The current data model represents one active physiotherapist-created protocol per patient. It does not force a patient to perform every exercise in the dataset; the assigned protocol determines the current exercise plan.

## 4. Video selection and deletion workflow

The upload/camera flow was updated in:

`recovery-monitor-frontend/src/components/UploadPanel.jsx`

Previously, choosing a file or stopping a recording immediately sent the video for analysis. The flow now gives the patient control first:

1. Record or choose a video.
2. Preview the selected video.
3. Choose **Use this video** to begin analysis.
4. Choose **Discard video** to remove the local selection and pick another file.

For videos that have already been analysed:

- The patient can choose **Delete video** beside the latest session.
- A confirmation is shown before deletion.
- The existing backend `DELETE /api/sessions/{session_id}` endpoint removes the original video, annotated video, thumbnail, analysis results, check-in, and review data for that session.

This lets patients replace an incorrect recording without changing their exercise protocol.

## 5. Therapist dashboard work

The therapist route is:

`#/physio`

The therapist dashboard now includes:

- Care-team workspace heading.
- “Today’s care pulse” hero section.
- Local-analysis status indicator.
- Priority-session call to action.
- Needs-attention count.
- Priority/pain review count.
- Active-patient count.
- Queue filters: All, Priority, Movement.
- Larger review thumbnails.
- Clearer patient cards with plan and awaiting-review context.
- Responsive behavior for smaller screens.
- Hover elevation and press feedback.
- Reduced-motion, reduced-transparency, and high-contrast fallbacks.

The existing therapist workflow is preserved:

- Click a flagged session to open the session review.
- Inspect the video and pose overlay.
- Jump between repetitions using the chart or `J`/`K` keyboard controls.
- Review rep-level model flags.
- Inspect pain and stiffness check-in data.
- Send a reference video and note to the patient.
- Approve or request changes.

The session review page continues to use the existing review API and does not replace the physiotherapist’s decision with an automated decision.

## 6. Session-review layout fix

The review page had horizontal overflow that could visually squeeze or clip the sidebar. The layout was hardened by:

- Applying `min-width: 0` to review columns and session-player containers.
- Preventing video elements from exceeding their panel width.
- Constraining charts and media to their available width.
- Preventing horizontal page overflow.

## 7. Tailscale and phone access

The frontend is served locally by Vite on port `5173`. Tailscale Serve exposes that local frontend to devices on the same tailnet.

Important behavior:

- `127.0.0.1` means the current device only.
- A phone or Mac must use the Tailscale HTTPS hostname, not its own `127.0.0.1` address.
- The Tailscale VPN must be connected on the client device.
- The `tailscale serve` command must remain active.
- Vite `server.allowedHosts` and `preview.allowedHosts` were updated to accept the tailnet host variants used during setup.

The backend remains local on port `8000`, and Vite proxies `/api` requests to it.

## 8. Service verification

The following checks succeeded during the session:

- Backend health endpoint returned `200 OK`.
- Frontend proxy health endpoint returned `200 OK`.
- Therapist review queue returned two flagged sessions.
- Patient endpoint returned two sample patients.
- Vite served the application successfully.
- The frontend was restarted in a persistent terminal session after the dashboard changes.

## 9. Current model and edge-device discussion

The current production movement pipeline is:

`Video → MediaPipe Pose Landmarker → joint features → rep segmentation → rules + XGBoost → therapist review`

Current components:

- MediaPipe Pose Landmarker Full for the main squat pipeline.
- MediaPipe Pose Landmarker Lite in the legacy seated-leg-extension path.
- XGBoost squat classifier with 200 trees, maximum depth 3, and 19 input features.
- Handcrafted movement features, quality checks, angle calculations, and rep segmentation.

The checked-in XGBoost artifact contains 1,968 tree nodes and 1,084 leaves. The artifact is approximately 190 KB.

There is currently no Hugging Face model, transformer, LLM, or VLM in the application.

The proposed next direction is to keep pose estimation and measurement deterministic, then add a local quantized LLM/VLM layer for:

- Therapist session summaries.
- Patient-friendly explanations.
- Cross-session progress summaries.
- Camera framing and exercise-context checks.
- Local care-plan drafting.

The LLM/VLM should explain and contextualize measured evidence rather than replace the auditable pose and measurement pipeline.

## 10. Quantized edge-AI direction

A sensible prototype progression is:

1. Start with a compact 7B–8B instruct model in 4-bit quantization.
2. Use LoRA/QLoRA adapters for therapist-style summaries and patient language.
3. Benchmark latency, memory, and quality on the ZGX Nano.
4. Test a 14B model if the smaller model is insufficient.
5. Treat a 30B model as a stretch benchmark, not an automatic requirement.

This gives the ZGX Nano a stronger role as a private local inference hub for pose analysis, video processing, and local language/multimodal assistance, while avoiding unnecessary cloud AI calls.

## 11. Files changed in the implementation commit

- `recovery-monitor-frontend/src/App.jsx`
- `recovery-monitor-frontend/src/components/UploadPanel.jsx`
- `recovery-monitor-frontend/src/pages/PatientHome.jsx`
- `recovery-monitor-frontend/src/pages/PhysioQueue.jsx`
- `recovery-monitor-frontend/src/styles.css`
- `recovery-monitor-frontend/vite.config.js`
- `recovery-monitor-frontend/src/assets/exercise-library-strip.png`
- `recovery-monitor-frontend/src/assets/rehab-motion-person.png`
- `recovery-monitor-frontend/src/assets/rehab-motion-person-standing.png`

## 12. Important limitations

- The application is still a demo experience using public sample data.
- It is not a medical device or clinical diagnosis system.
- The current model-backed production path is strongest for squats.
- Other exercises in REHAB24-6 still require exercise-specific pipeline work.
- No authentication system has been implemented yet; role access is currently demo routing.
- The current code runs MediaPipe on the device CPU; GPU acceleration and local LLM/VLM inference are future work.
