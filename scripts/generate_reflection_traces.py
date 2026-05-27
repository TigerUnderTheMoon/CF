"""Generate GSM8K reasoning traces with explicit reflection tags."""

from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import Any

import jsonlines
import torch
from datasets import load_dataset
from transformers import AutoModelForCausalLM, AutoTokenizer, set_seed


REFLECTION_RE = re.compile(
    r"<reflection(?:\s+type=[\"'](?P<type>[^\"']+)[\"'])?\s*>"
    r"(?P<content>.*?)"
    r"</reflection>",
    flags=re.IGNORECASE | re.DOTALL,
)
FINAL_ANSWER_RE = re.compile(r"final\s+answer\s*:\s*(?P<answer>.+)", re.IGNORECASE)
NUMBER_RE = re.compile(r"[-+]?\d[\d,]*(?:\.\d+)?")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate reflection-tagged GSM8K traces with a local HF causal LM."
    )
    parser.add_argument(
        "--model-name-or-path",
        required=True,
        help="Local path or HuggingFace model id for a causal language model.",
    )
    parser.add_argument("--split", default="train", help="GSM8K split or slice.")
    parser.add_argument("--max-samples", type=int, default=10)
    parser.add_argument("--max-input-tokens", type=int, default=2048)
    parser.add_argument("--max-new-tokens", type=int, default=512)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--top-p", type=float, default=0.95)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--device-map", default=None, help="Use 'auto' for accelerate sharding.")
    parser.add_argument(
        "--torch-dtype",
        default="auto",
        choices=["auto", "float16", "bfloat16", "float32"],
    )
    parser.add_argument(
        "--prompt-file",
        type=Path,
        default=Path(__file__).resolve().parents[1] / "prompts" / "reflection_generation.txt",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs") / "reflection_traces" / "gsm8k_reflection_traces.jsonl",
    )
    parser.add_argument("--trust-remote-code", action="store_true")
    return parser.parse_args()


def resolve_dtype(dtype_name: str) -> Any:
    if dtype_name == "auto":
        return "auto"
    return {
        "float16": torch.float16,
        "bfloat16": torch.bfloat16,
        "float32": torch.float32,
    }[dtype_name]


def build_prompt(template: str, question: str) -> str:
    if "{question}" in template:
        return template.format(question=question)
    return f"{template.rstrip()}\n\nQuestion:\n{question}\n"


def model_input_device(model: AutoModelForCausalLM) -> torch.device:
    return next(model.parameters()).device


def extract_reflection_spans(text: str, tokenizer: AutoTokenizer) -> list[dict[str, Any]]:
    spans = []
    for match in REFLECTION_RE.finditer(text):
        raw_content = match.group("content")
        content = raw_content.strip()
        leading_chars = len(raw_content) - len(raw_content.lstrip())
        content_start = match.start("content") + leading_chars
        prefix_tokens = tokenizer.encode(text[:content_start], add_special_tokens=False)
        content_tokens = tokenizer.encode(content, add_special_tokens=False)
        spans.append(
            {
                "start_token": len(prefix_tokens),
                "end_token": len(prefix_tokens) + len(content_tokens),
                "reflection_type": (match.group("type") or "self-reflection").strip(),
                "content": content,
            }
        )
    return spans


def extract_final_answer(text: str) -> str:
    matches = list(FINAL_ANSWER_RE.finditer(text))
    if matches:
        return matches[-1].group("answer").strip()
    return ""


def normalize_answer(text: str) -> str:
    if "####" in text:
        text = text.split("####")[-1]
    numbers = NUMBER_RE.findall(text)
    if numbers:
        return numbers[-1].replace(",", "")
    return text.strip().lower()


def is_correct(final_answer: str, reference_answer: str) -> bool:
    if not final_answer:
        return False
    return normalize_answer(final_answer) == normalize_answer(reference_answer)


def generate_trace(
    question: str,
    prompt_template: str,
    tokenizer: AutoTokenizer,
    model: AutoModelForCausalLM,
    args: argparse.Namespace,
) -> str:
    prompt = build_prompt(prompt_template, question)
    inputs = tokenizer(
        prompt,
        return_tensors="pt",
        truncation=True,
        max_length=args.max_input_tokens,
    )
    inputs = {key: value.to(model_input_device(model)) for key, value in inputs.items()}

    generation_kwargs = {
        "max_new_tokens": args.max_new_tokens,
        "do_sample": args.temperature > 0.0,
        "pad_token_id": tokenizer.eos_token_id,
    }
    if args.temperature > 0.0:
        generation_kwargs["temperature"] = args.temperature
        generation_kwargs["top_p"] = args.top_p

    with torch.no_grad():
        generated = model.generate(**inputs, **generation_kwargs)

    new_tokens = generated[0, inputs["input_ids"].shape[1] :]
    return tokenizer.decode(new_tokens, skip_special_tokens=True).strip()


def main() -> None:
    args = parse_args()
    set_seed(args.seed)

    prompt_template = args.prompt_file.read_text(encoding="utf-8")
    dataset = load_dataset("gsm8k", "main", split=args.split)
    if args.max_samples is not None:
        dataset = dataset.select(range(min(args.max_samples, len(dataset))))

    tokenizer = AutoTokenizer.from_pretrained(
        args.model_name_or_path,
        trust_remote_code=args.trust_remote_code,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        args.model_name_or_path,
        torch_dtype=resolve_dtype(args.torch_dtype),
        device_map=args.device_map,
        trust_remote_code=args.trust_remote_code,
    )
    if args.device_map is None:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model.to(device)
    model.eval()

    args.output.parent.mkdir(parents=True, exist_ok=True)
    generation_config = {
        "dataset": "gsm8k",
        "dataset_config": "main",
        "split": args.split,
        "max_new_tokens": args.max_new_tokens,
        "temperature": args.temperature,
        "top_p": args.top_p,
        "seed": args.seed,
        "prompt_file": str(args.prompt_file),
    }

    with jsonlines.open(args.output, mode="w") as writer:
        for idx, sample in enumerate(dataset):
            reasoning_trace = generate_trace(
                sample["question"],
                prompt_template,
                tokenizer,
                model,
                args,
            )
            final_answer = extract_final_answer(reasoning_trace)
            writer.write(
                {
                    "task_id": f"gsm8k-{args.split}-{idx}",
                    "question": sample["question"],
                    "reasoning_trace": reasoning_trace,
                    "reflection_spans": extract_reflection_spans(reasoning_trace, tokenizer),
                    "final_answer": final_answer,
                    "correctness": is_correct(final_answer, sample["answer"]),
                    "model_name": args.model_name_or_path,
                    "generation_config": generation_config,
                }
            )

    print(f"Wrote {len(dataset)} traces to {args.output}")


if __name__ == "__main__":
    main()
