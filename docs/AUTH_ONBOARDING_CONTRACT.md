# Recovery Monitor — Auth and Onboarding Contract

**Status:** Initial implementation contract  
**Owners:** Aishwarya — backend; Prajwal — frontend

## Roles

The first version supports two primary roles:

```text
patient
therapist
```

## Authentication API

### `POST /api/auth/signup`

Request:

```json
{
  "email": "patient@example.com",
  "password": "development-password",
  "role": "patient"
}
```

Response: `201 Created`

```json
{
  "user": { "id": "user-123", "email": "patient@example.com", "role": "patient" },
  "onboarding_completed": false
}
```

### `POST /api/auth/login`

Request:

```json
{ "email": "patient@example.com", "password": "development-password" }
```

Response: `200 OK` with the authentication mechanism selected by the backend, preferably an HTTP-only session cookie.

### `GET /api/auth/me`

Returns the current user and onboarding state. Returns `401 Unauthorized` when not signed in.

### `POST /api/auth/logout`

Invalidates the current session and returns `204 No Content`.

## Onboarding API

### `GET /api/onboarding`

Returns the current user profile and completion state.

### `PUT /api/onboarding/patient`

```json
{
  "name": "Jordan Mitchell",
  "affected_areas": ["knee"],
  "goals": ["improve_strength", "daily_activities"],
  "consent_local_analysis": true
}
```

### `PUT /api/onboarding/therapist`

```json
{
  "name": "Dr. Example",
  "specializations": ["lower_body", "general_mobility"],
  "supported_exercises": ["squat", "leg_lunge", "leg_abduction"]
}
```

Both onboarding endpoints return:

```json
{
  "user": { "id": "user-123", "email": "example@example.com", "role": "patient" },
  "profile": {},
  "onboarding_completed": true
}
```

## Patient intake API

### `POST /api/patient/intakes`

```json
{
  "affected_areas": ["knee"],
  "issue_types": ["pain_during_movement", "instability"],
  "when_it_happens": ["during_movement", "after_exercise"],
  "pain_score": 5,
  "duration": "one_to_three_months",
  "trend": "worsening",
  "limitations": ["incomplete_movement"],
  "goals": ["improve_strength"],
  "notes": "Squats feel harder than last week."
}
```

Response: `201 Created`

```json
{
  "id": "intake-123",
  "patient_user_id": "user-123",
  "status": "pending",
  "created_at": "2026-09-25T12:00:00Z"
}
```

Allowed statuses:

```text
pending, under_review, plan_drafted, approved, changes_requested, escalated
```

### `GET /api/patient/intakes`

Returns only the signed-in patient's own intakes.

## Therapist plan API

### `GET /api/therapist/intakes?status=pending`

Returns intakes assigned to the signed-in therapist or care team.

### `POST /api/therapist/intakes/{intake_id}/plan`

```json
{
  "exercise": "squat",
  "reference_video_id": 1,
  "target_reps": 8,
  "target_sets": 2,
  "target_depth_deg": 95,
  "pain_threshold": 5,
  "instructions": "Use a side view and stop if pain increases.",
  "notes": "Start with a controlled range of motion."
}
```

### `POST /api/therapist/plans/{plan_id}/approve`

```json
{ "notes": "Approved for the first week." }
```

### `POST /api/therapist/plans/{plan_id}/request-changes`

```json
{ "notes": "Reduce the target depth and repeat the check-in." }
```

Patients must not receive a new plan until a therapist approves it.

## Structured option values

Affected areas: `shoulder_arm`, `elbow_forearm`, `wrist_hand`, `back_core`, `hip`, `knee`, `ankle_foot`, `general_mobility`, `other`.

Issue types: `pain_during_movement`, `weakness`, `limited_range_of_motion`, `balance_or_stability`, `difficulty_walking`, `difficulty_exercising`, `recovery_after_injury_or_procedure`, `general_conditioning`, `other`.

When it happens: `at_rest`, `during_movement`, `after_exercise`, `during_specific_exercise`, `intermittently`, `not_sure`.

Trend: `improving`, `unchanged`, `worsening`, `not_sure`.

Dataset exercises: `arm_abduction`, `arm_vw`, `push_ups`, `leg_abduction`, `leg_lunge`, `squat`.

## Development users

Use local-only seed accounts:

```text
patient.demo@example.com
therapist.demo@example.com
```

Passwords must be hashed. Never commit real credentials or tokens.

## Permission rules

- Patients can read and edit only their own profile, intake, plans, and sessions.
- Therapists can access only assigned patient data.
- Therapists can create, edit, approve, or request changes to assigned patient plans.
- Endpoints must derive identity from the authenticated session, not trust browser-supplied patient IDs.
- Existing demo routes may remain available only as development access.

## Work split

### Aishwarya

- Add database tables and schema versioning.
- Implement authentication and password hashing.
- Implement onboarding, intake, and plan endpoints.
- Seed development users.
- Add permission and workflow tests.

### Prajwal

- Build sign-in and sign-up screens.
- Build role selection and onboarding screens.
- Build the patient intake form using these option values.
- Build therapist intake and plan approval screens.
- Add API client methods matching this document.

If this contract changes, update it first and notify the other developer before changing implementation code.
