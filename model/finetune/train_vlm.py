"""LoRA fine-tuning of Qwen3-VL-4B on REHAB24-6 reps (all 6 exercises).

    ~/ft-venv/bin/python -m model.finetune.train_vlm --epochs 3

Vision encoder frozen; LoRA adapters on the language model's attention and MLP layers. Loss only on
the answer tokens. Validates on person 5 after every epoch and keeps the best adapter by val loss.
Output: ~/rm-data/vlm/runs/<name>/ (adapter + training log).
"""

import argparse
import json
import math
import random
import time

import torch
from peft import LoraConfig, get_peft_model
from PIL import Image
from transformers import AutoProcessor, Qwen3VLForConditionalGeneration

from model.finetune.vlm_common import BASE_MODEL, DATA, load_split, messages, target


def encode(processor, row):
    """Token ids for prompt+answer, with labels masked to the answer only."""
    img = Image.open(DATA / row["image"]).convert("RGB")
    full = processor.apply_chat_template(messages("img", target(row)), tokenize=False)
    prompt = processor.apply_chat_template(messages("img"), tokenize=False, add_generation_prompt=True)
    enc = processor(text=[full], images=[img], return_tensors="pt")
    n_prompt = processor(text=[prompt], images=[img], return_tensors="pt")["input_ids"].shape[1]
    labels = enc["input_ids"].clone()
    labels[:, :n_prompt] = -100
    enc["labels"] = labels
    return enc


@torch.no_grad()
def val_loss(model, processor, rows):
    model.eval()
    total, n = 0.0, 0
    for row in rows:
        enc = {k: v.to(model.device) for k, v in encode(processor, row).items()}
        total += model(**enc).loss.item()
        n += 1
    model.train()
    return total / max(n, 1)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--epochs", type=int, default=3)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--rank", type=int, default=16)
    ap.add_argument("--accum", type=int, default=8)
    ap.add_argument("--name", default="qwen3vl4b_lora")
    ap.add_argument("--limit", type=int, default=None, help="debug: use only N training rows")
    args = ap.parse_args()

    torch.manual_seed(0)
    random.seed(0)
    out = DATA / "runs" / args.name
    out.mkdir(parents=True, exist_ok=True)

    processor = AutoProcessor.from_pretrained(BASE_MODEL)
    model = Qwen3VLForConditionalGeneration.from_pretrained(BASE_MODEL, dtype=torch.bfloat16, device_map="cuda")
    model.gradient_checkpointing_enable()
    model.enable_input_require_grads()
    lora = LoraConfig(r=args.rank, lora_alpha=2 * args.rank, lora_dropout=0.05, bias="none",
                      target_modules=r".*language_model.*\.(q_proj|k_proj|v_proj|o_proj|gate_proj|up_proj|down_proj)")
    model = get_peft_model(model, lora)
    model.print_trainable_parameters()

    train = load_split("train")[: args.limit]
    val = load_split("val")
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=args.lr, weight_decay=0.0)
    steps = math.ceil(len(train) / args.accum) * args.epochs
    sched = torch.optim.lr_scheduler.LambdaLR(
        opt, lambda s: min(1.0, (s + 1) / 20) * max(0.05, 0.5 * (1 + math.cos(math.pi * s / steps))))

    log, best, step = [], float("inf"), 0
    t0 = time.time()
    model.train()
    for epoch in range(args.epochs):
        random.shuffle(train)
        run = 0.0
        for i, row in enumerate(train):
            enc = {k: v.to(model.device) for k, v in encode(processor, row).items()}
            loss = model(**enc).loss / args.accum
            loss.backward()
            run += loss.item()
            if (i + 1) % args.accum == 0 or i + 1 == len(train):
                torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
                opt.step()
                sched.step()
                opt.zero_grad()
                step += 1
                if step % 10 == 0:
                    print(f"epoch {epoch + 1} step {step}/{steps} loss {run / 10:.4f} "
                          f"lr {sched.get_last_lr()[0]:.2e} {time.time() - t0:.0f}s", flush=True)
                    log.append({"step": step, "epoch": epoch + 1, "train_loss": run / 10})
                    run = 0.0
        vl = val_loss(model, processor, val)
        print(f"== epoch {epoch + 1} val loss {vl:.4f} ({time.time() - t0:.0f}s)", flush=True)
        log.append({"epoch": epoch + 1, "val_loss": vl})
        if vl < best:
            best = vl
            model.save_pretrained(out / "adapter")
            print("   saved best adapter", flush=True)
    json.dump({"args": vars(args), "log": log, "best_val_loss": best, "train_examples": len(train),
               "minutes": round((time.time() - t0) / 60, 1)}, open(out / "train_log.json", "w"), indent=1)


if __name__ == "__main__":
    main()
