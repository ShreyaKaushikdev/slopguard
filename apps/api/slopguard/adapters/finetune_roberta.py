#!/usr/bin/env python
"""Fine-tune RoBERTa on WHY vs WHAT labeled dataset.

This script trains a RoBERTa classifier to distinguish between:
- WHY sentences: causal reasoning, explanations, justifications
- WHAT sentences: declarative statements, action descriptions, facts

Usage:
    python finetune_roberta.py --dataset data/whywhat.jsonl --output models/whywhat-roberta

Dataset format (JSONL, one example per line):
    {"text": "because profiling showed 340ms latency", "label": "why"}
    {"text": "updated the billing module", "label": "what"}
    {"text": "the function returns a boolean", "label": "what"}
    {"text": "since the cache was stale, we added invalidation", "label": "why"}

Labels: "why", "what", or "neutral"

The script produces:
- A fine-tuned RoBERTa model in the output directory
- Evaluation metrics (accuracy, F1, confusion matrix)
- A training log with loss curves

Requirements:
    pip install transformers datasets accelerate torch
"""

import argparse
import json
import logging
import os
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

LABEL_MAP = {"why": 0, "what": 1, "neutral": 2}
ID_MAP = {0: "why", 1: "what", 2: "neutral"}


@dataclass
class TrainingConfig:
    model_name: str = "roberta-base"
    dataset_path: str = ""
    output_dir: str = "models/whywhat-roberta"
    max_length: int = 128
    batch_size: int = 16
    learning_rate: float = 2e-5
    num_epochs: int = 3
    warmup_ratio: float = 0.1
    weight_decay: float = 0.01
    seed: int = 42


def load_dataset(path: str) -> list[dict]:
    """Load JSONL dataset."""
    examples = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            item = json.loads(line)
            text = item.get("text", "").strip()
            label = item.get("label", "neutral").lower()
            if text and label in LABEL_MAP:
                examples.append({"text": text, "label": LABEL_MAP[label]})
    logger.info("Loaded %d examples from %s", len(examples), path)

    # Log label distribution
    counts = {}
    for ex in examples:
        label_name = ID_MAP[ex["label"]]
        counts[label_name] = counts.get(label_name, 0) + 1
    logger.info("Label distribution: %s", counts)

    return examples


def create_synthetic_dataset() -> list[dict]:
    """Create a synthetic WHY/WHAT dataset for bootstrapping.

    This generates labeled examples from linguistic patterns.
    Use this to bootstrap training when no labeled dataset is available.
    Replace with real labeled data for production use.
    """
    why_patterns = [
        "because {X} was causing {Y}",
        "since {X} led to {Y}",
        "to prevent {X} from happening",
        "so that {X} would not {Y}",
        "therefore we needed to {X}",
        "due to {X} affecting {Y}",
        "as a result of {X} failing",
        "in order to fix {X}",
        "because profiling showed {X}ms latency",
        "since the {X} was {Y}",
        "to avoid {X} issues",
        "because {X} broke when {Y}",
        "so that users can {X}",
        "to reduce {X} by {Y}%",
        "because the {X} was slow",
        "since we noticed {X} in production",
        "to ensure {X} works correctly",
        "because tests were failing for {X}",
        "as {X} reported {Y} errors",
        "to handle the case where {X}",
    ]

    what_patterns = [
        "updated the {X} module",
        "added {X} functionality",
        "fixed {X} bug",
        "removed unused {X} code",
        "renamed {X} to {Y}",
        "created {X} component",
        "implemented {X} feature",
        "changed {X} configuration",
        "bumped {X} to version {Y}",
        "added tests for {X}",
        "refactored {X} class",
        "updated documentation for {X}",
        "the function returns {X}",
        "added {X} endpoint",
        "modified {X} to handle {Y}",
        "created a new {X} service",
        "updated the {X} dependency",
        "fixed a typo in {X}",
        "added logging to {X}",
        "the {X} module handles {Y}",
    ]

    fillers = {
        "X": ["auth", "billing", "cache", "database", "api", "middleware", "frontend", "backend",
              "parser", "validator", "handler", "router", "service", "component", "hook"],
        "Y": ["timeout", "errors", "latency", "crashes", "duplicates", "memory leaks",
              "race conditions", "deadlocks", "overflow", "corruption"],
    }

    import random
    random.seed(42)

    examples = []

    for pattern in why_patterns:
        for _ in range(50):
            text = pattern
            for key, values in fillers.items():
                text = text.replace("{" + key + "}", random.choice(values))
            examples.append({"text": text, "label": LABEL_MAP["why"]})

    for pattern in what_patterns:
        for _ in range(50):
            text = pattern
            for key, values in fillers.items():
                text = text.replace("{" + key + "}", random.choice(values))
            examples.append({"text": text, "label": LABEL_MAP["what"]})

    # Add neutral examples
    neutrals = [
        "this is a test", "hello world", "the quick brown fox",
        "import os", "from typing import List", "def main():",
        "class Foo:", "export default function", "const x = 1",
        "print('hello')", "return True", "if __name__ == '__main__':",
    ]
    for n in neutrals:
        for _ in range(20):
            examples.append({"text": n, "label": LABEL_MAP["neutral"]})

    random.shuffle(examples)
    logger.info("Generated %d synthetic examples", len(examples))
    return examples


def train(config: TrainingConfig):
    """Fine-tune RoBERTa on WHY/WHAT dataset."""
    try:
        import torch
        from transformers import (
            AutoModelForSequenceClassification,
            AutoTokenizer,
            TrainingArguments,
            Trainer,
            DataCollatorWithPadding,
        )
        from datasets import Dataset
        from sklearn.model_selection import train_test_split
        from sklearn.metrics import accuracy_score, f1_score, precision_recall_fscore_support
    except ImportError:
        print("Error: Required packages not installed.")
        print("Run: pip install transformers datasets accelerate torch scikit-learn")
        return

    # Load or generate dataset
    if config.dataset_path and Path(config.dataset_path).exists():
        examples = load_dataset(config.dataset_path)
    else:
        print("No dataset provided. Generating synthetic dataset for bootstrapping...")
        examples = create_synthetic_dataset()
        # Save synthetic dataset
        output_path = Path(config.output_dir) / "synthetic_dataset.jsonl"
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            for ex in examples:
                f.write(json.dumps({"text": ex["text"], "label": ID_MAP[ex["label"]]}) + "\n")
        print(f"Saved synthetic dataset to {output_path}")

    # Split
    train_data, eval_data = train_test_split(examples, test_size=0.15, random_state=config.seed, stratify=[e["label"] for e in examples])

    # Tokenize
    tokenizer = AutoTokenizer.from_pretrained(config.model_name)
    train_dataset = Dataset.from_list(train_data)
    eval_dataset = Dataset.from_list(eval_data)

    def tokenize_fn(batch):
        return tokenizer(batch["text"], truncation=True, max_length=config.max_length)

    train_dataset = train_dataset.map(tokenize_fn, batched=True)
    eval_dataset = eval_dataset.map(tokenize_fn, batched=True)

    train_dataset = train_dataset.remove_columns(["text"])
    eval_dataset = eval_dataset.remove_columns(["text"])
    train_dataset = train_dataset.rename_column("label", "labels")
    eval_dataset = eval_dataset.rename_column("label", "labels")

    # Model
    model = AutoModelForSequenceClassification.from_pretrained(
        config.model_name,
        num_labels=3,
        problem_type="single_label_classification",
    )

    # Training args
    training_args = TrainingArguments(
        output_dir=config.output_dir,
        eval_strategy="epoch",
        save_strategy="epoch",
        learning_rate=config.learning_rate,
        per_device_train_batch_size=config.batch_size,
        per_device_eval_batch_size=config.batch_size,
        num_train_epochs=config.num_epochs,
        weight_decay=config.weight_decay,
        warmup_ratio=config.warmup_ratio,
        load_best_model_at_end=True,
        metric_for_best_model="f1",
        fp16=torch.cuda.is_available(),
        logging_steps=50,
        save_total_limit=2,
        seed=config.seed,
    )

    # Metrics
    def compute_metrics(pred):
        labels = pred.label_ids
        preds = pred.predictions.argmax(-1)
        precision, recall, f1, _ = precision_recall_fscore_support(labels, preds, average="weighted")
        acc = accuracy_score(labels, preds)
        return {"accuracy": acc, "f1": f1, "precision": precision, "recall": recall}

    # Train
    data_collator = DataCollatorWithPadding(tokenizer)
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=train_dataset,
        eval_dataset=eval_dataset,
        tokenizer=tokenizer,
        data_collator=data_collator,
        compute_metrics=compute_metrics,
    )

    print(f"Training for {config.num_epochs} epochs...")
    trainer.train()

    # Evaluate
    results = trainer.evaluate()
    print(f"\nEvaluation results:")
    for k, v in results.items():
        print(f"  {k}: {v:.4f}")

    # Save
    trainer.save_model(config.output_dir)
    tokenizer.save_pretrained(config.output_dir)
    print(f"\nModel saved to {config.output_dir}")

    # Export for use in SlopGuard
    adapter_path = Path(__file__).parent / "roberta_whywhat.py"
    print(f"\nTo use this model, update the model path in {adapter_path}:")
    print(f'  model="{config.output_dir}"')


def main():
    parser = argparse.ArgumentParser(description="Fine-tune RoBERTa on WHY/WHAT dataset")
    parser.add_argument("--dataset", default="", help="Path to JSONL dataset")
    parser.add_argument("--output", default="models/whywhat-roberta", help="Output directory")
    parser.add_argument("--model", default="roberta-base", help="Base model name")
    parser.add_argument("--epochs", type=int, default=3, help="Number of training epochs")
    parser.add_argument("--batch-size", type=int, default=16, help="Batch size")
    parser.add_argument("--lr", type=float, default=2e-5, help="Learning rate")
    parser.add_argument("--seed", type=int, default=42, help="Random seed")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO)

    config = TrainingConfig(
        model_name=args.model,
        dataset_path=args.dataset,
        output_dir=args.output,
        num_epochs=args.epochs,
        batch_size=args.batch_size,
        learning_rate=args.lr,
        seed=args.seed,
    )

    train(config)


if __name__ == "__main__":
    main()
