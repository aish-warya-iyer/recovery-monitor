"""Shared pieces for fine-tuning and evaluating the rep-understanding VLM."""

import json
import re
from pathlib import Path

DATA = Path.home() / "rm-data" / "vlm"
BASE_MODEL = str(Path.home() / "models" / "Qwen3-VL-4B-Instruct")
EXERCISES = ["squat", "leg_lunge", "leg_abduction", "arm_abduction", "arm_vw", "push_ups"]
VIEWS = ["side", "half_profile", "front"]

PROMPT = (
    "The image shows 8 frames in time order (left to right, top row then bottom row) from ONE repetition of a "
    "rehabilitation exercise.\n"
    "Exercises: squat, leg_lunge, leg_abduction, arm_abduction, arm_vw (arms move between a V and a W shape), "
    "push_ups (hands on a table).\n"
    "Camera views: side, half_profile, front.\n"
    'Answer with JSON only: {"exercise": ..., "correct": true or false, "view": ...}'
)


def target(row: dict) -> str:
    return json.dumps({"exercise": row["exercise"], "correct": row["correct"], "view": row["view"]})


def load_split(split: str) -> list[dict]:
    return [json.loads(l) for l in open(DATA / f"{split}.jsonl")]


def messages(image_path: str, answer: str | None = None) -> list[dict]:
    m = [{"role": "user", "content": [{"type": "image", "image": image_path}, {"type": "text", "text": PROMPT}]}]
    if answer is not None:
        m.append({"role": "assistant", "content": [{"type": "text", "text": answer}]})
    return m


def parse(text: str) -> dict:
    """Best-effort parse of the model's JSON answer; unknown fields become None."""
    m = re.search(r"\{.*\}", text, re.S)
    try:
        d = json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        d = {}
    ex = d.get("exercise")
    view = d.get("view")
    correct = d.get("correct")
    if isinstance(correct, str):
        correct = {"true": True, "false": False}.get(correct.lower())
    return {"exercise": ex if ex in EXERCISES else None,
            "correct": correct if isinstance(correct, bool) else None,
            "view": view if view in VIEWS else None,
            "valid_json": bool(d)}
