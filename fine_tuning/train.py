#!/usr/bin/env python3
"""Fine-tune Llama 3.1 8B with Unsloth + LoRA on ROCm."""

from __future__ import annotations

import math
from pathlib import Path
from typing import Any, Dict

from datasets import load_dataset
from transformers import TrainerCallback, TrainingArguments
from trl import SFTTrainer
from unsloth import FastLanguageModel


class EpochMetricsPrinter(TrainerCallback):
    """Prints train/eval losses and perplexity at each evaluation epoch."""

    def __init__(self) -> None:
        self._last_train_loss: float | None = None

    def on_log(self, args, state, control, logs: Dict[str, Any] | None = None, **kwargs):
        if logs and "loss" in logs and "eval_loss" not in logs:
            self._last_train_loss = float(logs["loss"])

    def on_evaluate(
        self, args, state, control, metrics: Dict[str, Any] | None = None, **kwargs
    ):
        metrics = metrics or {}
        epoch = metrics.get("epoch", state.epoch)
        eval_loss = metrics.get("eval_loss")
        if eval_loss is None:
            return

        eval_loss = float(eval_loss)
        perplexity = math.exp(eval_loss) if eval_loss < 100 else float("inf")
        train_loss_str = (
            f"{self._last_train_loss:.6f}" if self._last_train_loss is not None else "n/a"
        )
        print(
            f"[epoch {epoch:.2f}] train_loss={train_loss_str} "
            f"eval_loss={eval_loss:.6f} perplexity={perplexity:.6f}"
        )


def format_conversation(example: Dict[str, Any], tokenizer) -> Dict[str, str]:
    messages = example.get("messages", [])
    text = tokenizer.apply_chat_template(
        messages,
        tokenize=False,
        add_generation_prompt=False,
    )
    return {"text": text}


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    dataset_dir = root / "fine_tuning" / "dataset"
    output_dir = root / "fine_tuning" / "mairs-llama-3.1-8b"

    train_path = dataset_dir / "train.jsonl"
    val_path = dataset_dir / "val.jsonl"
    if not train_path.exists() or not val_path.exists():
        raise FileNotFoundError(
            "Expected dataset splits at fine_tuning/dataset/train.jsonl and val.jsonl. "
            "Run fine_tuning/prepare_dataset.py first."
        )

    model, tokenizer = FastLanguageModel.from_pretrained(
        model_name="unsloth/Meta-Llama-3.1-8B-Instruct",
        max_seq_length=2048,
        load_in_4bit=True,
    )

    model = FastLanguageModel.get_peft_model(
        model,
        r=16,
        lora_alpha=16,
        target_modules=[
            "q_proj",
            "k_proj",
            "v_proj",
            "o_proj",
            "gate_proj",
            "up_proj",
            "down_proj",
        ],
        lora_dropout=0,
        bias="none",
        use_gradient_checkpointing="unsloth",
        random_state=42,
    )

    dataset = load_dataset(
        "json",
        data_files={"train": str(train_path), "validation": str(val_path)},
    )

    train_dataset = dataset["train"].map(
        lambda ex: format_conversation(ex, tokenizer),
        remove_columns=dataset["train"].column_names,
    )
    eval_dataset = dataset["validation"].map(
        lambda ex: format_conversation(ex, tokenizer),
        remove_columns=dataset["validation"].column_names,
    )

    training_args = TrainingArguments(
        output_dir=str(output_dir),
        num_train_epochs=3,
        per_device_train_batch_size=4,
        gradient_accumulation_steps=4,
        learning_rate=2e-4,
        warmup_ratio=0.1,
        lr_scheduler_type="cosine",
        fp16=True,
        bf16=False,
        logging_strategy="epoch",
        evaluation_strategy="epoch",
        save_strategy="epoch",
        report_to="none",
        seed=42,
    )

    trainer = SFTTrainer(
        model=model,
        tokenizer=tokenizer,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        dataset_text_field="text",
        max_seq_length=2048,
        args=training_args,
        packing=False,
    )
    trainer.add_callback(EpochMetricsPrinter())

    trainer.train()
    trainer.save_model(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))

    final_eval = trainer.evaluate()
    final_eval_loss = float(final_eval["eval_loss"])
    final_perplexity = math.exp(final_eval_loss) if final_eval_loss < 100 else float("inf")
    print(
        f"[final] eval_loss={final_eval_loss:.6f} perplexity={final_perplexity:.6f} "
        f"output_dir={output_dir}"
    )


if __name__ == "__main__":
    main()
