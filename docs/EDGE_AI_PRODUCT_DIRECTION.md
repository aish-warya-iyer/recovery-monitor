# Recovery Monitor: Edge-AI Product Direction

**Status:** Proposal for team review  
**Purpose:** Align the product workflow and define the model-research work needed before implementation.

## 1. The product idea

Recovery Monitor is a private, local-first rehabilitation assistant. A patient describes a problem, records rehabilitation exercises, and receives understandable feedback. The HP ZGX Nano performs the sensitive video and language processing locally whenever possible.

The system should not replace a physiotherapist or make an autonomous diagnosis. Its job is to turn patient input and exercise videos into structured evidence, explanations, and proposed next steps for therapist approval.

The central product promise is:

> Turn rehabilitation videos and patient-reported symptoms into private, explainable movement evidence and therapist-approved care plans on the local edge device.

## 2. Confirmed dataset facts

The local REHAB24-6 dataset is stored outside the repository at:

```text
/home/hp21/rm-data
```

The dataset contains six exercise categories:

| Exercise ID | Dataset exercise | Suggested area |
|---|---|---|
| 1 | `arm_abduction` | Upper body |
| 2 | `arm_vw` | Upper body |
| 3 | `push_ups` | Upper body |
| 4 | `leg_abduction` | Lower body |
| 5 | `leg_lunge` | Lower body |
| 6 | `squat` | Lower body |

The dataset includes videos, 2D joints, 3D motion-capture joints, repetition segmentation, camera-view labels, and correctness labels. It is useful for training and evaluating exercise-specific movement models.

It should not be treated as a clinical diagnosis dataset. The people are healthy volunteers acting out movement errors, and the labels describe exercise performance rather than medical conditions.

The current application pipeline is strongest for squats:

```text
Video → MediaPipe Pose → joint features → repetition segmentation → rules/XGBoost → therapist review
```

The other five exercises are represented in the dataset but need their own validated inference pipelines before they are presented as equally supported product features.

## 3. Proposed user workflow

```text
Landing page
    ↓
Sign up / sign in
    ↓
Choose role: Patient or Therapist
    ↓
Role-specific onboarding
    ↓
Patient selects structured issue options and adds optional text
    ↓
Structured issue extraction; optional audio transcription can be added later
    ↓
Safety and red-flag screening
    ↓
Match patient with therapist specialization
    ↓
Draft exercise plan and explanation
    ↓
Therapist reviews, edits, approves, or rejects
    ↓
Patient receives approved videos and targets
    ↓
Patient records an exercise session
    ↓
HP ZGX Nano performs local movement analysis
    ↓
Evidence summary and progress explanation
    ↓
Therapist review when confidence is low or risk is elevated
```

### Patient onboarding

The first version should use selectable options instead of asking the patient to describe everything from scratch. This makes onboarding easier to complete, produces consistent data for matching, and gives the LLM a reliable structured input.

- Name and contact information
- Affected area: shoulder/arm, back/core, hip, knee, ankle/foot, or general mobility
- Main issue: pain, weakness, reduced range of motion, balance, stiffness, instability, or difficulty exercising
- When it happens: at rest, during movement, after exercise, or only during a specific exercise
- Severity: pain score from 0–10
- Duration: less than a week, 1–4 weeks, 1–3 months, more than 3 months, or not sure
- Trend: improving, unchanged, or worsening
- Limitations: incomplete movement, instability, one-sided difference, swelling/stiffness, fear of movement, or none
- Goal: daily activities, strength, range of motion, sport/work, reduced discomfort, or follow a therapist plan
- Optional short text explanation
- Relevant consent and privacy choices
- Preferred therapist area, if known

The patient should not be asked to choose a clinical diagnosis. Guided selections and optional text are converted into a structured summary for therapist review.

### Therapist onboarding

Therapists should select one or more specialization areas and supported exercises:

- Upper-body rehabilitation
- Lower-body rehabilitation
- General or full-body rehabilitation
- Shoulder and arm movement
- Back and core movement
- Hip and knee movement
- Ankle and gait-related movement
- Supported exercises from the exercise catalog

Specialization is for routing and matching, not for automatically deciding treatment. A therapist can review patients outside their selected areas if the product supports that workflow.

## 4. What each model should do

The project should separate model responsibilities instead of asking one model to do everything.

### Exercise and video models

These models should:

- Detect whether the intended person and body parts are visible
- Identify or verify the exercise
- Estimate pose and joint landmarks
- Segment repetitions
- Calculate exercise-specific measurements
- Estimate movement quality and confidence
- Produce evidence linked to frames or repetitions

These outputs should remain structured and auditable.

### Optional speech recognition

Audio is not required for the first version. If audio is added later, Whisper or another local ASR model can convert a patient audio description into text. The transcript should be shown or confirmed before it is used for planning.

### Language model

The local language model should:

- Summarize the patient’s issue in plain language
- Extract structured fields from text or transcript
- Explain movement evidence to the patient
- Summarize progress over multiple sessions
- Draft a proposed exercise plan for therapist approval
- Explain why a session was flagged
- Help therapists review sessions efficiently

The language model should not:

- Diagnose a medical condition
- Claim that a patient is safe without appropriate review
- Invent measurements that the movement pipeline did not produce
- Choose a final treatment plan without therapist approval
- Replace the deterministic movement measurements

### Optional vision-language model

A VLM may be evaluated later for camera framing, exercise-context checks, and high-level video questions. It should be compared against the structured pose pipeline rather than automatically replacing it.

## 5. Why edge AI instead of cloud-only AI?

Cloud processing is technically possible. The edge-device advantage is the combination of:

- Raw patient videos staying on the local device
- Lower latency for immediate exercise feedback
- Operation when internet access is poor or unavailable
- Lower recurring per-video inference cost
- Local control over data retention
- A clearer privacy and security story for clinics
- Auditable evidence generation before any optional cloud sharing

The product should be described as **local-first**, not necessarily cloud-never. Optional cloud features may be added later for encrypted backups, team synchronization, or aggregated model improvement, subject to consent.

## 6. Model research assignment

The model-research team should investigate models by capability, not only by parameter count.

### A. Local speech-to-text

Compare Whisper-family and other ASR models for:

- Accuracy on conversational patient speech
- English and required future languages
- Memory use on the HP ZGX Nano
- Real-time or near-real-time performance
- Offline packaging and license

### B. Local text LLM

Compare compact instruct models suitable for:

- Structured extraction into JSON
- Patient-friendly explanations
- Therapist summaries
- Plan drafting with strict output schemas
- Reliable refusal and escalation behavior
- Local inference latency and memory use

Candidate model size should be selected from measurements on the Nano. Start with a small quantized model and test larger models only if quality requires it.

### C. Optional local VLM

Investigate whether a VLM adds value for:

- Camera-position guidance
- Person/body-part visibility checks
- Exercise-context verification
- Explaining visible movement in conjunction with measured pose data

Do not use a VLM as the only correctness judge until it is evaluated against the labeled dataset and the existing structured pipeline.

### D. Exercise movement models

For each of the six exercises, document:

- Required landmarks
- Camera-view requirements
- Repetition segmentation method
- Exercise-specific measurements
- Correctness labels and limitations
- Minimum data and evaluation set
- Edge-device throughput

## 7. Evaluation matrix

Every candidate model should be evaluated on the HP ZGX Nano, not only on a development laptop.

| Dimension | Measurement |
|---|---|
| Quality | Task-specific accuracy and human review score |
| Reliability | Invalid output rate, hallucination rate, and refusal behavior |
| Latency | Time to first result and total session time |
| Memory | Peak RAM and GPU memory |
| Throughput | Videos or sessions processed per hour |
| Privacy | Whether raw data leaves the device |
| Offline behavior | Whether the complete workflow works without internet |
| Reproducibility | Same input produces stable structured output |
| Licensing | Model and dataset license compatibility |
| Maintainability | Quantization, packaging, and update complexity |

For the LLM, test structured scenarios such as:

1. Clear patient issue with enough information.
2. Ambiguous issue requiring a follow-up question.
3. High pain or possible red flag requiring therapist escalation.
4. Conflicting video evidence and patient description.
5. Low-confidence or poor-camera-quality session.
6. Unsupported exercise.
7. Request for a diagnosis.

## 8. Proposed safety boundary

The system should use three outcomes:

### Informational

The system explains measured evidence and gives general education. No care-plan change is proposed.

### Draft for therapist approval

The system proposes an exercise, target, or adjustment based on the patient profile and evidence. The patient does not receive it until a therapist approves it.

### Escalate to therapist

The system detects high pain, concerning language, low confidence, poor video quality, unexpected movement, or an unsupported situation. It pauses automated planning and routes the case to a therapist.

## 9. Suggested database additions

The existing database contains patients, protocols, sessions, check-ins, reviews, and reference videos. Authentication and the proposed workflow will need additional entities:

```text
users
patient_profiles
therapist_profiles
therapist_specializations
care_relationships
patient_intakes
intake_transcripts
plan_drafts
plan_approvals
exercise_catalog
model_runs
```

Important design rule: preserve the original movement evidence and model version for every session. A later model update must not silently rewrite historical results.

## 10. Recommended implementation phases

### Phase 1: Product and data foundation

- Confirm patient, therapist, and admin roles.
- Define the onboarding questions.
- Define red-flag and escalation behavior with a clinical reviewer.
- Add the six-exercise catalog.
- Add authentication and care relationships.

### Phase 2: Therapist-approved planning

- Patient text intake first.
- Structured issue summary.
- Therapist review queue for new patient requests.
- Draft plan with exercise, video, repetitions, and explanation.
- Approval/edit/reject workflow.

### Phase 3: Audio and local intelligence

- Add local Whisper transcription.
- Add a local LLM for structured extraction and summaries.
- Add model-run logging, confidence, and evidence references.
- Benchmark the selected models on the Nano.

### Phase 4: Exercise expansion

- Keep squat as the reference implementation.
- Build and validate the other five exercise pipelines one at a time.
- Do not expose an exercise as clinically supported until its camera and accuracy limits are documented.

### Phase 5: Learning from therapist feedback

- Store therapist corrections and approvals.
- Separate product-time inference from offline training.
- Evaluate whether corrections improve movement models, prompts, or routing.
- Never train on patient data without explicit consent and governance.

## 11. Questions for team review

1. Which patient conditions and use cases are in scope for the first release?
2. Which therapist roles and specialization categories do we want to support?
3. Which languages are required for text and audio intake?
4. Is the first LLM responsible only for summaries and plan drafts, or also for exercise-context checks?
5. Which outputs require mandatory therapist approval?
6. What is the minimum acceptable latency on the HP ZGX Nano?
7. Which of the six exercises will be supported in the first demo?
8. What data can be retained locally, and what data—if any—may be synchronized to the cloud?

## Proposed decision

The direction is technically and product-wise reasonable if we define the LLM as a local reasoning and communication layer around auditable movement analysis. The first implementation should not attempt to train one model to understand raw videos, diagnose patients, and prescribe treatment. It should combine specialized models, structured evidence, strict safety boundaries, and therapist approval.
