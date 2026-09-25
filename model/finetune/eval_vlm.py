"""Score the VLM on held-out people, before and after fine-tuning.

    ~/ft-venv/bin/python -m model.finetune.eval_vlm --split test                      # base model, zero-shot
    ~/ft-venv/bin/python -m model.finetune.eval_vlm --split test --adapter qwen3vl4b_lora

Reports exercise accuracy, view accuracy, correct/incorrect accuracy + F1 for "incorrect", per
exercise, valid-JSON rate and seconds per rep. Writes model/results/vlm_<name>_<split>.json.
"""

import argparse
import json
import time
from collections import defaultdict
from pathlib import Path

import torch
from PIL import Image
from sklearn.metrics import f1_score
from transformers import AutoProcessor, Qwen3VLForConditionalGeneration

from model.finetune.vlm_common import BASE_MODEL, DATA, EXERCISES, load_split, messages, parse

RESULTS = Path(__file__).resolve().parents[1] / "results"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--split", default="test")
    ap.add_argument("--adapter", default=None, help="run name under ~/rm-data/vlm/runs")
    ap.add_argument("--limit", type=int, default=None)
    args = ap.parse_args()

    processor = AutoProcessor.from_pretrained(BASE_MODEL)
    processor.tokenizer.padding_side = "left"
    model = Qwen3VLForConditionalGeneration.from_pretrained(BASE_MODEL, dtype=torch.bfloat16, device_map="cuda")
    if args.adapter:
        from peft import PeftModel

        model = PeftModel.from_pretrained(model, DATA / "runs" / args.adapter / "adapter")
    model.eval()

    rows = load_split(args.split)[: args.limit]
    preds, t0 = [], time.time()
    for i, row in enumerate(rows):
        img = Image.open(DATA / row["image"]).convert("RGB")
        prompt = processor.apply_chat_template(messages("img"), tokenize=False, add_generation_prompt=True)
        enc = processor(text=[prompt], images=[img], return_tensors="pt").to(model.device)
        with torch.no_grad():
            out = model.generate(**enc, max_new_tokens=48, do_sample=False)
        text = processor.batch_decode(out[:, enc["input_ids"].shape[1]:], skip_special_tokens=True)[0]
        preds.append(parse(text) | {"raw": text})
        if (i + 1) % 50 == 0:
            print(f"{i + 1}/{len(rows)} {time.time() - t0:.0f}s", flush=True)
    secs = (time.time() - t0) / max(len(rows), 1)

    def acc(key, subset=None):
        idx = subset if subset is not None else range(len(rows))
        idx = list(idx)
        return round(sum(preds[i][key] == rows[i][key] for i in idx) / max(len(idx), 1), 3)

    def f1_incorrect(idx):
        y = [not rows[i]["correct"] for i in idx]
        p = [preds[i]["correct"] is False for i in idx]
        return round(f1_score(y, p, zero_division=0), 3)

    per_ex = defaultdict(list)
    for i, r in enumerate(rows):
        per_ex[r["exercise"]].append(i)
    out = {
        "model": "Qwen3-VL-4B-Instruct" + (f" + LoRA ({args.adapter})" if args.adapter else " (zero-shot)"),
        "split": args.split, "people": sorted({r["person"] for r in rows}), "n": len(rows),
        "valid_json": round(sum(p["valid_json"] for p in preds) / len(rows), 3),
        "exercise_accuracy": acc("exercise"), "view_accuracy": acc("view"),
        "correctness_accuracy": acc("correct"), "incorrect_f1": f1_incorrect(range(len(rows))),
        "per_exercise": {e: {"n": len(per_ex[e]), "exercise_accuracy": acc("exercise", per_ex[e]),
                             "correctness_accuracy": acc("correct", per_ex[e]),
                             "incorrect_f1": f1_incorrect(per_ex[e])} for e in EXERCISES if per_ex[e]},
        "seconds_per_rep": round(secs, 2),
        "examples": [{"image": r["image"], "truth": {k: r[k] for k in ("exercise", "correct", "view")},
                      "pred": preds[i]["raw"]} for i, r in enumerate(rows[:10])],
    }
    RESULTS.mkdir(exist_ok=True)
    name = args.adapter or "zeroshot"
    (RESULTS / f"vlm_{name}_{args.split}.json").write_text(json.dumps(out, indent=1))
    print(json.dumps({k: v for k, v in out.items() if k not in ("examples", "per_exercise")}, indent=1))
    for e, v in out["per_exercise"].items():
        print(f"  {e:14} {v}")


if __name__ == "__main__":
    main()
