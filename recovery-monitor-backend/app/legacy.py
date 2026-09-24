"""Original seated-leg-extension analysis (rules only, MediaPipe lite). Kept unchanged for the
`seated_leg_extension` exercise; squats go through the model pipeline in model/analyze.py."""

from __future__ import annotations

import math
from pathlib import Path
from urllib.request import urlretrieve

import cv2
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision


MODEL_PATH = Path(__file__).resolve().parents[1] / "pose_landmarker_lite.task"

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
