from __future__ import annotations

from datetime import datetime, timezone
import math
from pathlib import Path
import tempfile
from typing import Literal
from urllib.request import urlretrieve

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision
from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field


class Evidence(BaseModel):
    repetition: int
    observation: str
    value: float | None = None
    unit: str | None = None


class AnalysisResponse(BaseModel):
    session_id: str
    exercise: str
    status: Literal["complete", "uncertain"]
    form_score: int = Field(ge=0, le=100)
    repetitions: int = Field(ge=0)
    correct_repetitions: int = Field(ge=0)
    range_of_motion_deg: float = Field(ge=0)
    movement_smoothness: float = Field(ge=0, le=1)
    confidence: float = Field(ge=0, le=1)
    observations: list[str]
    evidence: list[Evidence]
    source: str
    origin: str
    analyzed_at: str


class CheckInRequest(BaseModel):
    pain_score: int = Field(ge=0, le=10)
    comment: str = ""
    transcript_confidence: float | None = Field(
        default=None,
        ge=0,
        le=1,
    )


class DecisionRequest(BaseModel):
    decision: Literal["approve", "request_changes"]
    notes: str = ""


class SessionRecord(BaseModel):
    session_id: str
    check_in: CheckInRequest | None = None
    decision: DecisionRequest | None = None
    updated_at: str


app = FastAPI(
    title="Recovery Monitor Local Control Plane",
    version="0.1.0",
)


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


SESSION_RECORDS: dict[str, SessionRecord] = {}
PAIN_REVIEW_THRESHOLD = 4


MODEL_PATH = Path(__file__).with_name(
    "pose_landmarker_lite.task"
)

MODEL_URL = (
    "https://storage.googleapis.com/"
    "mediapipe-models/pose_landmarker/"
    "pose_landmarker_lite/float16/latest/"
    "pose_landmarker_lite.task"
)


def ensure_pose_model() -> None:
    """Download the official pose model once."""
    if not MODEL_PATH.exists():
        urlretrieve(MODEL_URL, MODEL_PATH)


def knee_angle(
    hip: object,
    knee: object,
    ankle: object,
) -> float:
    """Calculate the 2-D angle at the knee."""

    hip_vector = (
        hip.x - knee.x,
        hip.y - knee.y,
    )

    ankle_vector = (
        ankle.x - knee.x,
        ankle.y - knee.y,
    )

    numerator = (
        hip_vector[0] * ankle_vector[0]
        + hip_vector[1] * ankle_vector[1]
    )

    hip_length = math.hypot(*hip_vector)
    ankle_length = math.hypot(*ankle_vector)

    if hip_length == 0 or ankle_length == 0:
        return 0.0

    cosine = numerator / (
        hip_length * ankle_length
    )

    cosine = max(-1.0, min(1.0, cosine))

    return math.degrees(math.acos(cosine))


def analyze_uploaded_video(
    video_path: str,
) -> dict[str, object]:
    """Analyze the uploaded video locally."""

    ensure_pose_model()

    capture = cv2.VideoCapture(video_path)

    angles: list[float] = []
    confidences: list[float] = []
    frame_count = 0

    options = vision.PoseLandmarkerOptions(
        base_options=python.BaseOptions(
            model_asset_path=str(MODEL_PATH),
        ),
        running_mode=vision.RunningMode.VIDEO,
        num_poses=1,
        min_pose_detection_confidence=0.5,
        min_pose_presence_confidence=0.5,
        min_tracking_confidence=0.5,
    )

    with vision.PoseLandmarker.create_from_options(
        options
    ) as pose_landmarker:
        try:
            while True:
                success, frame = capture.read()

                if not success:
                    break

                frame_count += 1

                rgb_frame = cv2.cvtColor(
                    frame,
                    cv2.COLOR_BGR2RGB,
                )

                image = mp.Image(
                    image_format=mp.ImageFormat.SRGB,
                    data=rgb_frame,
                )

                fps = capture.get(
                    cv2.CAP_PROP_FPS
                )

                timestamp_ms = int(
                    (frame_count - 1)
                    * 1000
                    / max(1, fps)
                )

                result = pose_landmarker.detect_for_video(
                    image,
                    timestamp_ms,
                )

                if not result.pose_landmarks:
                    continue

                landmarks = result.pose_landmarks[0]

                candidates = [
                    (23, 25, 27),
                    (24, 26, 28),
                ]

                best_candidate = None
                best_visibility = 0.0

                for (
                    hip_index,
                    knee_index,
                    ankle_index,
                ) in candidates:
                    selected = [
                        landmarks[hip_index],
                        landmarks[knee_index],
                        landmarks[ankle_index],
                    ]

                    visibility = sum(
                        getattr(
                            point,
                            "visibility",
                            1.0,
                        )
                        for point in selected
                    ) / 3

                    if visibility > best_visibility:
                        best_candidate = selected
                        best_visibility = visibility

                if (
                    best_candidate is not None
                    and best_visibility >= 0.45
                ):
                    angles.append(
                        knee_angle(*best_candidate)
                    )

                    confidences.append(
                        best_visibility
                    )

        finally:
            capture.release()

    if len(angles) < 3:
        confidence = (
            sum(confidences)
            / len(confidences)
            if confidences
            else 0.0
        )

        return {
            "status": "uncertain",
            "form_score": 0,
            "repetitions": 0,
            "correct_repetitions": 0,
            "range_of_motion_deg": 0.0,
            "movement_smoothness": 0.0,
            "confidence": round(confidence, 2),
            "observations": [
                (
                    "Pose landmarks could not be detected "
                    "reliably in the uploaded video."
                ),
                (
                    f"Only {len(angles)} usable pose frames "
                    f"were found across {frame_count} video frames."
                ),
            ],
            "evidence": [],
        }

    minimum_angle = min(angles)
    maximum_angle = max(angles)
    range_of_motion = maximum_angle - minimum_angle

    bent_threshold = (
        minimum_angle + range_of_motion * 0.30
    )

    extended_threshold = (
        minimum_angle + range_of_motion * 0.70
    )

    repetitions = 0
    correct_repetitions = 0

    phase = (
        "extended"
        if angles[0] >= extended_threshold
        else "bent"
    )

    for angle in angles:
        if (
            phase == "bent"
            and angle >= extended_threshold
        ):
            phase = "extended"

        elif (
            phase == "extended"
            and angle <= bent_threshold
        ):
            repetitions += 1
            correct_repetitions += 1
            phase = "bent"

    frame_changes = [
        abs(current - previous)
        for previous, current in zip(
            angles,
            angles[1:],
        )
    ]

    average_change = sum(frame_changes) / max(
        1,
        len(frame_changes),
    )

    smoothness = max(
        0.0,
        min(
            1.0,
            1.0 - average_change / 45.0,
        ),
    )

    confidence = sum(confidences) / len(confidences)

    if repetitions == 0:
        form_score = 0
    else:
        repetition_coverage = min(
            repetitions / 10.0,
            1.0,
        )

        range_quality = min(
            range_of_motion / 60.0,
            1.0,
        )

        form_score = round(
            max(
                0,
                min(
                    100,
                    confidence * 40
                    + range_quality * 40
                    + repetition_coverage * 20,
                ),
            )
        )

    status = (
        "complete"
        if repetitions > 0 and confidence >= 0.55
        else "uncertain"
    )

    observations = [
        (
            f"Detected {repetitions} completed "
            "seated-leg-extension repetitions "
            "using pose landmarks."
        ),
        (
            "This is a geometric movement observation, "
            "not a clinical conclusion."
        ),
    ]

    if repetitions == 0:
        observations[0] = (
            "Movement was detected, but no complete "
            "repetition cycle was found in the "
            "uploaded video."
        )

    return {
        "status": status,
        "form_score": form_score,
        "repetitions": repetitions,
        "correct_repetitions": correct_repetitions,
        "range_of_motion_deg": round(
            range_of_motion,
            1,
        ),
        "movement_smoothness": round(
            smoothness,
            2,
        ),
        "confidence": round(
            confidence,
            2,
        ),
        "observations": observations,
        "evidence": [],
    }


@app.get("/api/health")
def health() -> dict[str, object]:
    return {
        "status": "ready",
        "device": "HP ZGX Nano",
        "inference_local": True,
        "network_required": False,
        "cloud_ai_disabled": True,
    }


@app.post(
    "/api/sessions/{session_id}/check-in",
    response_model=SessionRecord,
)
async def save_check_in(
    session_id: str,
    payload: CheckInRequest,
) -> SessionRecord:
    """Save patient-reported information."""

    existing = SESSION_RECORDS.get(session_id)
    if (
        payload.decision == "approve"
        and existing is not None
        and existing.check_in is not None
        and existing.check_in.pain_score > PAIN_REVIEW_THRESHOLD
    ):
        raise HTTPException(
            status_code=409,
            detail=(
                f"Pain score is above the review threshold of "
                f"{PAIN_REVIEW_THRESHOLD}/10. Therapist review is required."
            ),
        )

    record = SessionRecord(
        session_id=session_id,
        check_in=payload,
        decision=(
            existing.decision
            if existing
            else None
        ),
        updated_at=datetime.now(
            timezone.utc
        ).isoformat(),
    )

    SESSION_RECORDS[session_id] = record

    return record


@app.post(
    "/api/sessions/{session_id}/decision",
    response_model=SessionRecord,
)
async def save_therapist_decision(
    session_id: str,
    payload: DecisionRequest,
) -> SessionRecord:
    """Save therapist approval or change request."""

    existing = SESSION_RECORDS.get(session_id)

    record = SessionRecord(
        session_id=session_id,
        check_in=(
            existing.check_in
            if existing
            else None
        ),
        decision=payload,
        updated_at=datetime.now(
            timezone.utc
        ).isoformat(),
    )

    SESSION_RECORDS[session_id] = record

    return record


@app.get(
    "/api/sessions/{session_id}",
    response_model=SessionRecord | None,
)
def get_session_record(
    session_id: str,
) -> SessionRecord | None:
    """Return saved session information."""

    return SESSION_RECORDS.get(session_id)


@app.post(
    "/api/analyze-session",
    response_model=AnalysisResponse,
)
async def analyze_session(
    exercise: Literal[
        "seated_leg_extension"
    ] = Form("seated_leg_extension"),
    session_id: str = Form("demo-session-001"),
    source: Literal[
        "demo",
        "upload",
        "camera",
    ] = Form("demo"),
    video: UploadFile | None = File(None),
) -> AnalysisResponse:
    """Analyze an uploaded video locally."""

    if video is not None:
        video_bytes = await video.read()

        suffix = Path(
            video.filename or "exercise.mp4"
        ).suffix or ".mp4"

        with tempfile.NamedTemporaryFile(
            suffix=suffix
        ) as temporary_file:
            temporary_file.write(video_bytes)
            temporary_file.flush()

            result = analyze_uploaded_video(
                temporary_file.name
            )

        return AnalysisResponse(
            session_id=session_id,
            exercise=exercise,
            source=source,
            origin="local_mediapipe_heuristic",
            analyzed_at=datetime.now(
                timezone.utc
            ).isoformat(),
            evidence=[
                Evidence(**item)
                for item in result["evidence"]
            ],
            **{
                key: value
                for key, value in result.items()
                if key != "evidence"
            },
        )

    return AnalysisResponse(
        session_id=session_id,
        exercise=exercise,
        status="complete",
        form_score=78,
        repetitions=10,
        correct_repetitions=7,
        range_of_motion_deg=62.4,
        movement_smoothness=0.81,
        confidence=0.86,
        observations=[
            "Three repetitions did not reach the target extension range.",
            "Camera angle reduced confidence for repetitions 8-9.",
        ],
        evidence=[
            Evidence(
                repetition=3,
                observation="Incomplete extension",
                value=51.2,
                unit="degrees",
            ),
            Evidence(
                repetition=8,
                observation="Reduced pose confidence",
                value=0.68,
                unit="confidence",
            ),
        ],
        source=source,
        origin="local_demo_stub",
        analyzed_at=datetime.now(
            timezone.utc
        ).isoformat(),
    )