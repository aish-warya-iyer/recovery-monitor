# Recovery Monitor — Codex Handoff

**Last updated:** 2026-09-25  
**Primary developer:** Prajwal  
**Purpose:** Context for continuing work with another Codex account.

## Project location

Prajwal's personal worktree:

```text
/home/hp21/Desktop/recovery-monitor-prajwal
```

Current branch:

```text
hp21/work
```

This branch tracks `origin/storyboard/landing-page`.

The original shared checkout is separate and should not be used for Prajwal's edits:

```text
/home/hp21/recovery-monitor
```

## Running services

Prajwal's services use separate ports:

```text
Frontend: http://127.0.0.1:5174/
Backend:  http://127.0.0.1:8001/
Health:   http://127.0.0.1:8001/api/health
```

Start the backend:

```bash
cd /home/hp21/Desktop/recovery-monitor-prajwal/recovery-monitor-backend
/home/hp21/rm-venv/bin/uvicorn main:app --reload --host 127.0.0.1 --port 8001
```

Start the frontend:

```bash
cd /home/hp21/Desktop/recovery-monitor-prajwal/recovery-monitor-frontend
env PATH=/home/hp21/.local/node/bin:$PATH /home/hp21/.local/node/bin/npm run dev -- --host 127.0.0.1 --port 5174
```

## Data and database

The training dataset is outside Git:

```text
/home/hp21/rm-data
```

It contains REHAB24-6 videos, 2D/3D joints, segmentation labels, and metadata.

Application data for this worktree:

```text
/home/hp21/Desktop/recovery-monitor-prajwal/recovery-monitor-backend/data
```

This is a separate SQLite copy from the original checkout. Do not commit SQLite files, videos, model archives, `node_modules`, or generated caches.

Current database snapshot:

```text
2 patients, 2 protocols, 7 sessions, 7 check-ins, 4 reviews, 1 reference video
```

## Existing application

Already implemented:

- Landing page
- Patient dashboard
- Therapist queue
- Therapist patient view
- Therapist session review
- Video upload/recording and local analysis
- Exercise evidence, repetition metrics, and therapist review
- Evaluation and privacy pages

Important frontend files:

```text
recovery-monitor-frontend/src/App.jsx
recovery-monitor-frontend/src/api.js
recovery-monitor-frontend/src/pages/PatientHome.jsx
recovery-monitor-frontend/src/pages/PhysioQueue.jsx
recovery-monitor-frontend/src/pages/PhysioPatient.jsx
recovery-monitor-frontend/src/pages/PhysioSession.jsx
recovery-monitor-frontend/src/components/UploadPanel.jsx
```

Current routes are hash-based demo routes such as:

```text
#/patient/jordan
#/patient/sam
#/physio
```

There is currently no real authentication or user identity system.

## Product direction

```text
Patient onboarding
  → structured issue intake
  → therapist review
  → therapist-approved exercise plan
  → patient records exercise video
  → HP ZGX Nano performs local movement analysis
  → evidence and explanation
  → therapist review when needed
```

The six dataset exercise categories are:

```text
arm_abduction
arm_vw
push_ups
leg_abduction
leg_lunge
squat
```

The current production pipeline is strongest for squats. The other exercises need exercise-specific validation before being presented as equally supported.

The LLM should explain structured movement evidence, summarize patient issues, and draft plans for therapist approval. It should not independently diagnose or prescribe treatment.

## Team split

Prajwal owns frontend and product workflow work:

- Sign-in/sign-up UI
- Role selection
- Patient onboarding
- Therapist onboarding
- Patient intake screens
- Therapist plan-review UI
- Connecting authenticated users to existing pages

Aishwarya owns backend, database, and API work:

- Users and authentication
- Password hashing and development seed users
- Patient/therapist profiles
- Specializations and care relationships
- Intake and plan APIs
- Therapist approval workflow
- Authentication guards and backend tests

Read:

- [TEAM_WORK_SPLIT.md](./TEAM_WORK_SPLIT.md)
- [EDGE_AI_PRODUCT_DIRECTION.md](./EDGE_AI_PRODUCT_DIRECTION.md)

## Immediate next tasks for Prajwal

1. Build `SignIn.jsx`, `SignUp.jsx`, and role selection.
2. Add a frontend auth state/context layer.
3. Add protected route behavior while backend auth is being implemented.
4. Build structured patient onboarding using selectable options.
5. Build therapist specialization onboarding.
6. Add patient intake and status screens.
7. Coordinate endpoint names and response shapes through `docs/API_CONTRACT.md`.

Suggested frontend files:

```text
recovery-monitor-frontend/src/auth/AuthContext.jsx
recovery-monitor-frontend/src/pages/SignIn.jsx
recovery-monitor-frontend/src/pages/SignUp.jsx
recovery-monitor-frontend/src/pages/RoleSelect.jsx
recovery-monitor-frontend/src/pages/PatientOnboarding.jsx
recovery-monitor-frontend/src/pages/TherapistOnboarding.jsx
recovery-monitor-frontend/src/pages/PatientIntake.jsx
recovery-monitor-frontend/src/pages/PlanReview.jsx
```

## Collaboration rules

- Do not work in `/home/hp21/recovery-monitor` for Prajwal's feature work.
- Do not have two people edit the same physical folder.
- Do not check out the same branch in two worktrees.
- Agree before editing `App.jsx`, `api.js`, `styles.css`, `db.py`, or `docs/API_CONTRACT.md`.
- Use focused commits and push each person's branch.
- Never force-push, reset another person's branch, or delete another person's worktree.

## Prompt for the next Codex account

```text
Continue Recovery Monitor work from docs/CODEX_HANDOFF.md.
Use /home/hp21/Desktop/recovery-monitor-prajwal as the active worktree and do not edit the shared checkout. Read docs/TEAM_WORK_SPLIT.md and docs/EDGE_AI_PRODUCT_DIRECTION.md before making changes. I am Prajwal, so focus on frontend authentication and structured onboarding unless I give a different task. Preserve the existing local data, services, and branch workflow. First inspect git status and confirm the current branch before editing.
```
