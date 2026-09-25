"""Local GPU service for the two neural models: the fine-tuned rep VLM and Whisper speech-to-text.

    ~/ft-venv/bin/uvicorn model.ai_service:app --host 127.0.0.1 --port 8100

Runs on the ZGX Nano's GPU and only listens on localhost. The backend sends it file paths on the same
machine (videos and audio never leave the device).

  GET  /health                  -> which models are loaded
  POST /vlm   {"images": [...]} -> per tiled-rep image: {"exercise", "correct", "view", "raw"}
  POST /asr   {"path": "..."}   -> {"text", "seconds"}
"""

import os
import threading
import time
from pathlib import Path

import torch
from fastapi import FastAPI, HTTPException
from PIL import Image
from pydantic import BaseModel

from model.finetune.vlm_common import BASE_MODEL, messages, parse

ADAPTER = Path(os.getenv("RM_VLM_ADAPTER", Path.home() / "rm-data/vlm/runs/qwen3vl4b_lora/adapter"))
WHISPER = Path(os.getenv("RM_WHISPER", Path.home() / "models/whisper-large-v3-turbo"))
VLM_BATCH = 8

app = FastAPI(title="Recovery Monitor local AI service")
_lock = threading.Lock()  # one GPU job at a time keeps latency predictable
_models: dict = {}


def vlm():
    if "vlm" not in _models:
        from peft import PeftModel
        from transformers import AutoProcessor, Qwen3VLForConditionalGeneration

        proc = AutoProcessor.from_pretrained(BASE_MODEL)
        proc.tokenizer.padding_side = "left"
        model = Qwen3VLForConditionalGeneration.from_pretrained(BASE_MODEL, dtype=torch.bfloat16, device_map="cuda")
        model = PeftModel.from_pretrained(model, ADAPTER).eval()
        _models["vlm"] = (proc, model)
    return _models["vlm"]


def whisper():
    if "asr" not in _models:
        from transformers import pipeline

        _models["asr"] = pipeline("automatic-speech-recognition", model=str(WHISPER), dtype=torch.float16,
                                  device="cuda")
    return _models["asr"]


@app.on_event("startup")
def warm():
    vlm()
    whisper()


@app.get("/health")
def health():
    return {"ok": True, "models": sorted(_models), "vlm": "Qwen3-VL-4B-Instruct + LoRA (REHAB24-6)",
            "asr": "whisper-large-v3-turbo", "device": torch.cuda.get_device_name(0)}


class VlmIn(BaseModel):
    images: list[str]


@app.post("/vlm")
def vlm_predict(body: VlmIn):
    for p in body.images:
        if not Path(p).is_file():
            raise HTTPException(404, f"image not found: {p}")
    proc, model = vlm()
    out, t0 = [], time.time()
    prompt = proc.apply_chat_template(messages("img"), tokenize=False, add_generation_prompt=True)
    with _lock, torch.no_grad():
        for i in range(0, len(body.images), VLM_BATCH):
            chunk = body.images[i:i + VLM_BATCH]
            imgs = [Image.open(p).convert("RGB") for p in chunk]
            enc = proc(text=[prompt] * len(imgs), images=imgs, return_tensors="pt", padding=True).to(model.device)
            gen = model.generate(**enc, max_new_tokens=48, do_sample=False)
            texts = proc.batch_decode(gen[:, enc["input_ids"].shape[1]:], skip_special_tokens=True)
            out.extend(parse(t) | {"raw": t} for t in texts)
    return {"predictions": out, "seconds": round(time.time() - t0, 2)}


class AsrIn(BaseModel):
    path: str


@app.post("/asr")
def asr(body: AsrIn):
    if not Path(body.path).is_file():
        raise HTTPException(404, "audio not found")
    import librosa

    audio, sr = librosa.load(body.path, sr=16000, mono=True)
    if len(audio) < 1600:
        raise HTTPException(422, "Recording is too short.")
    t0 = time.time()
    with _lock:
        res = whisper()({"raw": audio, "sampling_rate": 16000}, return_timestamps=True,
                        generate_kwargs={"language": "english", "task": "transcribe"})
    return {"text": res["text"].strip(), "audio_seconds": round(len(audio) / 16000, 1),
            "seconds": round(time.time() - t0, 2)}
