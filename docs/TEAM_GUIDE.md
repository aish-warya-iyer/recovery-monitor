# Recovery Monitor: team guide for testing, demo and pitch

**Deadline: today (Fri Sept 25), 8:00 PM.** Submission needs a public repo, an interactive deck and a
≤2-minute demo video. Judging is tomorrow.

The app is complete and running on the Nano. Our job now: **test it, record the demo, write the pitch.**
Please don't change code on the running branch; report bugs instead (section 6).

---

## 1. What the app does (say it like this)

A patient records a rehab exercise at home and says how it felt. The **HP ZGX Nano** analyses the video
and voice **on the device**, and the physiotherapist gets a review with evidence and a drafted report. The
physiotherapist decides; approved sessions become the patient's personal baseline.

| Piece | What it does | Where it runs |
|---|---|---|
| MediaPipe pose | finds 33 body points in every frame | Nano CPU |
| XGBoost (one per exercise, 6) | counts reps, measures angles, flags incorrect reps vs the patient's approved form | Nano CPU |
| **Our fine-tuned vision model** (Qwen3-VL-4B + LoRA, trained on REHAB24-6) | recognises the exercise and camera view, second opinion on each rep | Nano GPU |
| Whisper large-v3-turbo | patient's voice note → text | Nano GPU |
| Local LLM (Nemotron) | drafts the physio report from the measurements + the patient's words | Nano |

Six exercises: squat, lunge, leg raise to the side, arm raise to the side, arm V-W, push-ups (hands on table).

---

## 2. Open the app (5 minutes)

1. Connect to the Nano the usual way (Tailscale + VS Code **Remote-SSH**, user `hp21`).
2. In VS Code open the **Ports** tab (bottom panel) → **Add Port** → type **`8020`** → Enter.
3. Open **http://localhost:8020** in your laptop browser.

Other ports on the Nano (leave them alone): 8000/5173 older demo, 8100 AI models (GPU), 11434 local LLM.

## 3. Accounts (password for all: `recovery-demo`)

| Email | Role | What you'll see |
|---|---|---|
| `therapist.demo@example.com` | Physiotherapist | Review queue, all patients, plans, AI reports |
| `jordan@demo.local` | Patient | 3 past sessions, pain going down (improving) |
| `sam@demo.local` | Patient | Urgent case: all reps flagged, pain 3 → 6 |
| `test@demo.local` | Patient | **Real video of our friend** (squats) + voice note |
| `patient.demo@example.com` | New patient | Starts at onboarding (sign-up flow) |

You can also **create your own account** with Sign up (patient or therapist).
Demo patients are public sample data (REHAB24-6, CC BY-NC 4.0), except `test`, which is our own recording.

---

## 4. Test walkthroughs (each takes 5–10 minutes)

Tick each step; if anything looks wrong, note it (section 6).

### A. Physiotherapist
1. Sign in as `therapist.demo@example.com` → you land on the **Review queue**.
2. Sam's session should be first, marked **Urgent**. Open it.
3. Check: video with skeleton overlay · angle chart under it (click the chart → video jumps) · rep cards with
   reasons · **AI draft report** with red flags · the patient's pain.
4. Press **J / K** to move between reps. Mark one rep "Incorrect".
5. Try **Approve** without ticking the pain box → it must refuse. Tick it → Approve works.
6. Open **Patients → Test Patient** → change the plan's exercise (e.g. to *Arm raise to the side*) → Save.
7. Visit **Accuracy** and **Privacy** pages: every number should look sensible (no `NaN`).

### B. Patient (existing)
1. Sign in as `test@demo.local` (or `jordan@demo.local`).
2. Check today's plan and the reference video.
3. **Record with camera** (or Upload) a short clip, following the camera rule for the exercise:
   - squat, lunge → **side-on** to the camera
   - arm raise, leg raise, arm V-W, push-ups → **facing** the camera
   - whole body in frame, good light, 5–6 reps
4. Watch the live progress bar (convert → pose → analyse → render).
5. In "How did it feel?": pick a pain score, press **🎤 Tell us how it felt**, speak, check the text, send.
6. Sign out, sign in as the therapist → the new session and its AI report should appear in the queue.

### C. New patient, full journey
1. Sign in as `patient.demo@example.com` (or Sign up) → complete onboarding → submit the **intake** form
   (area, problem, pain, goals).
2. Sign in as the therapist → the request appears → **Claim** it.
3. Open the patient in **Patients** → set a plan (exercise, reps, pain alert) → Save.
4. Sign back in as the patient → the plan shows → record a session → check-in.

### D. The "smart" moments (use these in the demo)
| Try this | Expected |
|---|---|
| Upload an **arm raise** while the plan is **squat** | "This looks like arm raise, but your plan is squat" + flagged |
| Film a squat **from the front** | "Camera angle not ideal" / uncertain |
| Legs out of frame | Rejected with "step back so your legs are visible" |
| Say "my knee feels **swollen**" in the voice note | Red flag → **Urgent** in the queue |
| Access rules | A patient opening `#/physio` or another patient's page is sent back to their own portal |

---

## 5. Real-video recording list (for accuracy + demo footage)

Phone horizontal, 2.5–3 m away, waist height, still. Normal clothes. **Write down the true rep count and which
reps were done wrong on purpose** (put it in the file name).

| Exercise | Camera | Clip A (correct, 6 reps) | Clip B (6 reps with mistakes) |
|---|---|---|---|
| Squat | side | slow, deep | 2 shallow, 2 leaning forward, 2 too fast |
| Lunge | side | front knee ~90° | 3 knee past toes, 3 leaning |
| Leg raise to the side | front | same leg, straight | 3 leaning sideways, 3 barely lifting |
| Arm raise to the side | front | straight arm | 3 bent elbow, 3 shrugging |
| Arm V-W | front | full V → W | 3 uneven, 3 rushed |
| Push-ups (hands on table) | front | full range | 3 hips sagging, 3 half range |

Upload through the app (as `test@demo.local`), or copy files to `~/rm-data/real_tests/` on the Nano and tell
Arya. Get consent from anyone filmed; never commit videos to GitHub.

---

## 6. Reporting a problem

Post in the team chat (or a GitHub issue) with:
- **Account** you used · **page** (URL) · **what you did** · **what you expected** · **what happened**
- a screenshot, and the **session id** if it's about a video (last part of the URL)

Don't restart servers or switch branches on the Nano. Arya fixes and redeploys.

---

## 7. Who does what (until 8 PM)

| Task | Owner (suggested) | Done when |
|---|---|---|
| Walkthroughs A–D, report bugs | everyone, 20 min each | all ticked |
| Record real videos (section 5) | 2 people | 12 clips + notes |
| **Pitch script** (section 8) + Q&A answers | 1 person | 2-min script, rehearsed |
| **Deck** (problem → solution → architecture → results → impact) | 1 person | slides with the diagram and numbers below |
| **Demo video** ≤ 2 min (team name, tagline, logo, live app) | 1–2 people | uploaded, link ready |
| ZRT serving (HP points), setup script, README | Arya | pushed |
| Submission form | Arya + 1 | submitted by **5 PM** (3 h buffer) |

---

## 8. Demo script (≈ 2 minutes)

1. **Problem (15 s):** Most rehab happens at home, unsupervised. Physios can't see if exercises are done right,
   and patients' videos are private health data.
2. **Patient (35 s):** sign in as Test Patient → record squats → live on-device analysis → reps, depth, skeleton
   overlay → voice note "my knee feels a bit swollen".
3. **Physio (40 s):** queue shows it as **Urgent** → open → synced angle chart, flagged reps with reasons →
   **AI draft report** comparing what the patient said with what the video shows → approve and send.
4. **Smart checks (15 s):** upload an arm raise under a squat plan → "this looks like an arm raise".
5. **Trust (15 s):** Accuracy page: ±5.3° vs lab motion capture, 99% exercise recognition after fine-tuning,
   everything on the HP ZGX Nano, works offline.

### Numbers to quote (all measured, on people the models never saw)
| | |
|---|---|
| Knee angle vs 16-camera motion capture (side view) | **±5.3°** |
| Fine-tuned vision model: exercise recognition | **63% → 99%** |
| Camera-view recognition | **31% → 98%** |
| Incorrect-rep detection, 6 exercises (F1) | **0.62–0.85** |
| Voice to text | 11 s of speech in **0.25 s** |
| Full analysis of a 1-minute video | under a minute, on device |

### Honest answers for Q&A
- **Is it medical?** No. It's evidence for a physiotherapist, who makes every decision.
- **Training data?** REHAB24-6: 10 volunteers in motion-capture suits, physio-labelled reps. Real patients in
  home settings are the next validation step; we tested our own real videos too.
- **Why local?** Patient video is health data; nothing leaves the Nano, no cloud AI, works offline.
- **What did you train?** XGBoost per exercise on pose features, and a LoRA fine-tune of Qwen3-VL-4B on
  1,428 labelled reps. Whisper and the report model are used as-is, locally.
- **Weak spots?** Angle accuracy only measured for squats; the camera angle matters (we tell users how to film).
