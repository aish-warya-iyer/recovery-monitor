# Recovery Monitor Team Work Split

**People:** Prajwal and Aishwarya  
**Purpose:** Work in parallel without editing the same checkout, branch, or files.

## Important rule

Do not work from the same physical folder. A branch does not protect two people editing the same checkout at the same time.

Use two worktrees:

```text
/home/hp21/Desktop/recovery-monitor-prajwal      # Prajwal
/home/hp21/Desktop/recovery-monitor-aishwarya    # Aishwarya
```

Each person opens only their own folder in VS Code.

## Branch setup

The product baseline is `storyboard/landing-page` at commit `fb5097f`.

Prajwal's current worktree:

```text
branch: hp21/work
folder: /home/hp21/Desktop/recovery-monitor-prajwal
```

Aishwarya should create a separate worktree and branch:

```bash
cd /home/hp21/recovery-monitor
git fetch origin
git worktree add /home/hp21/Desktop/recovery-monitor-aishwarya \
  -b aishwarya/backend-auth origin/storyboard/landing-page
```

If that branch already exists:

```bash
git worktree add /home/hp21/Desktop/recovery-monitor-aishwarya \
  aishwarya/backend-auth
```

Never check out the same branch in both worktrees.

## Work ownership

### Prajwal: frontend and product workflow

Primary ownership:

```text
recovery-monitor-frontend/src/App.jsx
recovery-monitor-frontend/src/api.js
recovery-monitor-frontend/src/auth/
recovery-monitor-frontend/src/pages/
recovery-monitor-frontend/src/components/
recovery-monitor-frontend/src/styles.css
```

Tasks:

1. Sign-in, sign-up, sign-out, and current-user state.
2. Role selection and protected patient/therapist routes.
3. Patient onboarding with selectable issue options and optional text.
4. Therapist specialization onboarding.
5. Patient intake and intake-status screens.
6. Therapist intake queue and plan-review UI.
7. Connect the existing patient, therapist, upload, and review pages to authenticated users.

Prajwal should avoid changing backend Python files except for integration tests or an agreed API change.

### Aishwarya: backend, database, and API

Primary ownership:

```text
recovery-monitor-backend/app/db.py
recovery-monitor-backend/app/main.py
recovery-monitor-backend/app/auth/
recovery-monitor-backend/app/routes/
recovery-monitor-backend/app/seed.py
recovery-monitor-backend/tests/
docs/API_CONTRACT.md
```

Tasks:

1. Users, authentication sessions, password hashing, and development seed users.
2. Patient and therapist profiles.
3. Therapist specializations and care relationships.
4. Patient intake storage and status transitions.
5. Therapist plan drafts and approval/rejection endpoints.
6. Authentication guards for existing patient, session, and review APIs.
7. Backend tests for permissions and workflow transitions.

Aishwarya should avoid changing frontend JSX and CSS except for agreed integration fixes.

## API contract

Agree on these endpoints before implementing screens:

```text
POST /api/auth/signup
POST /api/auth/login
POST /api/auth/logout
GET  /api/auth/me

GET  /api/onboarding
PUT  /api/onboarding/patient
PUT  /api/onboarding/therapist

GET  /api/exercises
GET  /api/specializations

POST /api/patient/intakes
GET  /api/patient/intakes

GET  /api/therapist/intakes
GET  /api/therapist/intakes/{id}
POST /api/therapist/intakes/{id}/plan
POST /api/therapist/plans/{id}/approve
POST /api/therapist/plans/{id}/request-changes
```

The backend owner edits `docs/API_CONTRACT.md`. The frontend owner builds against that contract rather than inventing a second API shape. If an endpoint changes, update the contract and notify the other person first.

## Database entities

Aishwarya should add these without removing the existing demo data:

```text
users
auth_sessions
patient_profiles
therapist_profiles
therapist_specializations
care_relationships
patient_intakes
plan_drafts
plan_approvals
exercise_catalog
model_runs
```

Use migrations or a schema-version table. Back up the local SQLite database before schema work.

## Shared files to coordinate

These are conflict-prone:

```text
recovery-monitor-frontend/src/App.jsx
recovery-monitor-frontend/src/api.js
recovery-monitor-frontend/src/styles.css
recovery-monitor-backend/app/db.py
recovery-monitor-backend/app/main.py
docs/API_CONTRACT.md
```

Rules:

- Only one person edits a shared file at a time.
- Prefer new files over repeatedly editing central files.
- Keep shared-file changes small.
- Do not run repository-wide formatters.
- Do not commit `node_modules`, SQLite data, videos, model archives, or caches.

## Commit and integration

Each person commits and pushes only their own branch:

```bash
git status --short --branch
git add <your-files>
git commit -m "Describe one focused change"
git push -u origin <your-branch>
```

Use focused commits such as:

```text
Add authentication API and seeded users
Add patient onboarding form
Add therapist plan approval screen
Add intake permission tests
```

Integrate through a pull request or a deliberate merge into an integration branch. Do not copy folders manually, force-push, reset another person's branch, or delete another person's worktree.

## Implementation order

### 1. Contract and database foundation

Aishwarya defines authentication, onboarding, intake, and plan response shapes. Prajwal reviews them before building screens.

### 2. Authentication

Aishwarya implements the API and development users. Prajwal builds sign-in/sign-up screens against the contract.

### 3. Onboarding

Aishwarya implements profile and specialization storage. Prajwal implements patient and therapist onboarding screens.

### 4. Therapist-approved planning

Aishwarya implements intake, draft-plan, and approval APIs. Prajwal implements patient intake and therapist review screens.

### 5. Existing movement workflow

Connect approved plans to the existing patient dashboard, exercise videos, upload flow, local analysis, and therapist review queue.

### 6. Local AI integration

Only after the structured workflow works, add model-backed summaries and plan drafts. The model produces a draft for therapist approval, not an autonomous treatment decision.

## Daily coordination

At the start, run:

```bash
git status --short --branch
git fetch origin
```

Before editing a shared file, communicate the file, intended change, and expected duration. At the end, push the branch and tell the other person which API, database, or UI behavior changed.

## Development users

Use local-only seed accounts such as:

```text
patient.demo@example.com
therapist.demo@example.com
```

Passwords must be hashed. Never commit real passwords, tokens, production secrets, videos, or patient data.

## First milestone definition of done

- User can sign up and sign in.
- User selects a patient or therapist role.
- Each role completes onboarding.
- Patient submits a structured issue intake.
- Therapist sees the intake and drafts or edits a plan.
- Patient receives the plan only after therapist approval.
- Existing session analysis still works.
- Unauthorized users cannot access another patient's sessions.
- Backend tests cover authentication and permissions.
