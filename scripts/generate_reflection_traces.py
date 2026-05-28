"""Generate GSM8K reasoning traces with explicit reflection tags."""

from __future__ import annotations

import argparse
import json
import math
import re
import sys
from pathlib import Path
from typing import Any, Sequence


PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fma.io import load_records, write_records
from fma.generation import DiverseReflectionGenerator, ReflectionChain, ReflectionStyle
from fma.taxonomy import ReflectionTaxonomizer
from fma.types import ReflectionTrace


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
        default=None,
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
        default=Path("outputs") / "reflection_traces.jsonl",
    )
    parser.add_argument(
        "--synthetic-balanced",
        action="store_true",
        help="Generate deterministic category-balanced synthetic reflection chains.",
    )
    parser.add_argument(
        "--n-per-category",
        type=int,
        default=100,
        help="Synthetic traces per ReflectionStyle category.",
    )
    parser.add_argument(
        "--chain-length",
        type=int,
        default=3,
        help="Number of reflection steps per synthetic chain.",
    )
    parser.add_argument(
        "--category-sequence",
        default=None,
        help="Optional comma-separated category sequence for synthetic mixed chains.",
    )
    parser.add_argument(
        "--taxonomy",
        action="store_true",
        help="Annotate an existing reflection trace JSONL file with deterministic taxonomy labels.",
    )
    parser.add_argument(
        "--taxonomy-input",
        type=Path,
        default=Path("outputs") / "reflection_traces.jsonl",
        help="Input JSONL for --taxonomy mode.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print planned actions without writing files.")
    parser.add_argument("--trust-remote-code", action="store_true")
    return parser.parse_args()


def resolve_dtype(dtype_name: str) -> Any:
    import torch

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


def clamp_float(value: Any, low: float, high: float, fallback: float) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = fallback
    if not math.isfinite(number):
        number = fallback
    return min(high, max(low, number))


def first_reflection_text(record: dict[str, Any]) -> str:
    value = record.get("reflection_text")
    if isinstance(value, str):
        return value
    spans = record.get("reflection_spans") or record.get("metacognitive_spans") or []
    if isinstance(spans, list) and spans:
        content = spans[0].get("content") if isinstance(spans[0], dict) else None
        if isinstance(content, str):
            return content
    return str(record.get("reasoning_trace") or "")


def trace_id_for_record(record: dict[str, Any], index: int) -> str:
    return str(record.get("trace_id") or record.get("sample_id") or record.get("task_id") or f"trace_{index:03d}")


def task_difficulty(record: dict[str, Any]) -> int:
    value = int(clamp_float(record.get("task_difficulty"), 1.0, 5.0, 3.0))
    return min(5, max(1, value))


def intervention_magnitude(record: dict[str, Any]) -> float:
    if "intervention_magnitude" in record:
        return clamp_float(record["intervention_magnitude"], 0.0, 1.0, 0.0)

    spans = record.get("reflection_spans") or record.get("metacognitive_spans") or []
    span_length = 0
    if isinstance(spans, list) and spans and isinstance(spans[0], dict):
        span = spans[0]
        if "start_token" in span and "end_token" in span:
            span_length = max(0, int(span.get("end_token") or 0) - int(span.get("start_token") or 0))
        elif "span_length" in span:
            span_length = max(0, int(span.get("span_length") or 0))
        elif "content" in span:
            span_length = len(str(span.get("content") or "").split())
    token_count = max(1, len(str(record.get("reasoning_trace") or "").split()))
    return clamp_float(span_length / token_count, 0.0, 1.0, 0.0)


def reflection_trace_from_record(record: dict[str, Any], index: int) -> ReflectionTrace:
    trace_id = trace_id_for_record(record, index)
    return ReflectionTrace(
        trace_id=trace_id,
        reflection_text=first_reflection_text(record),
        task_id=str(record.get("task_id") or trace_id),
        task_difficulty=task_difficulty(record),
        intervention_magnitude=intervention_magnitude(record),
        locality_score=clamp_float(record.get("locality_score"), 0.0, 1.0, 1.0),
    )


def annotate_taxonomy(input_path: Path, output_path: Path, dry_run: bool = False) -> list[dict[str, Any]]:
    records = load_records(input_path)
    taxonomizer = ReflectionTaxonomizer()
    annotated: list[dict[str, Any]] = []

    for index, record in enumerate(records):
        trace = reflection_trace_from_record(record, index)
        annotation = taxonomizer.classify(trace)
        confidence = annotation.confidence
        if not math.isfinite(confidence) or confidence < 0.0 or confidence > 1.0:
            raise ValueError(f"Invalid taxonomy_confidence for trace_id={trace.trace_id!r}: {confidence!r}")
        annotated.append(
            {
                **record,
                "trace_id": trace.trace_id,
                "task_id": trace.task_id,
                "reflection_text": trace.reflection_text,
                "task_difficulty": trace.task_difficulty,
                "intervention_magnitude": trace.intervention_magnitude,
                "locality_score": trace.locality_score,
                "category": annotation.category.name,
                "taxonomy_confidence": confidence,
                "taxonomy_rationale": annotation.rationale,
            }
        )

    if dry_run:
        preview = [
            {
                "trace_id": record["trace_id"],
                "category": record["category"],
                "taxonomy_confidence": record["taxonomy_confidence"],
            }
            for record in annotated[:3]
        ]
        print(
            {
                "dry_run": True,
                "taxonomy_input": str(input_path),
                "output": str(output_path),
                "records": len(annotated),
                "preview": preview,
            }
        )
        return annotated

    write_records(annotated, output_path)
    print(f"Wrote {len(annotated)} taxonomy-annotated traces to {output_path}")
    return annotated


def parse_category_sequence(value: str | None) -> list[ReflectionStyle] | None:
    if value is None or not value.strip():
        return None
    categories: list[ReflectionStyle] = []
    for raw_name in value.split(","):
        normalized = raw_name.strip().upper().replace("-", "_")
        categories.append(ReflectionStyle[normalized])
    return categories


def synthetic_record_from_chain(
    chain: ReflectionChain,
    index: int,
    seed: int,
) -> dict[str, Any]:
    spans: list[dict[str, Any]] = []
    cursor = 0
    for step_index, step in enumerate(chain.reflection_chain):
        length = len(step.text.split())
        spans.append(
            {
                "start_token": cursor,
                "end_token": cursor + length,
                "reflection_type": step.category.lower(),
                "content": step.text,
                "step_index": step_index,
            }
        )
        cursor += length

    categories = chain.categories()
    primary_category = categories[0] if categories else "OTHER"
    return {
        "trace_id": chain.trace_id,
        "sample_id": chain.trace_id,
        "task_id": f"synthetic-reflection-{index:05d}",
        "task_type": "synthetic_reflection",
        "question": f"Synthetic reflection benchmark item {index}.",
        "reasoning_trace": chain.chain_text(),
        "reflection_text": chain.chain_text(),
        "reflection_chain": [step.to_dict() for step in chain.reflection_chain],
        "reflection_categories": categories,
        "reflection_spans": spans,
        "category": primary_category,
        "taxonomy_confidence": 1.0,
        "taxonomy_rationale": "synthetic category-conditioned template",
        "task_difficulty": 1 + (index % 5),
        "intervention_magnitude": [0.2, 0.5, 0.9][index % 3],
        "locality_score": [0.9, 0.6, 0.2][index % 3],
        "correctness": True,
        "final_answer": "synthetic",
        "reference_answer": "synthetic",
        "synthetic": True,
        "generation_config": {
            "mode": "synthetic_balanced",
            "seed": seed,
            "chain_length": len(chain),
        },
    }


def write_synthetic_records(records: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    if output_path.suffix.lower() == ".json":
        output_path.write_text(
            json.dumps(records, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return
    write_records(records, output_path)


def generate_synthetic_balanced(args: argparse.Namespace) -> list[dict[str, Any]]:
    generator = DiverseReflectionGenerator()
    sequence = parse_category_sequence(args.category_sequence)
    if sequence is not None:
        chains = generator.generate_chain(
            sequence,
            seed=args.seed,
            n=args.n_per_category * len(ReflectionStyle),
        )
    else:
        chains = generator.generate_balanced(
            n_per_category=args.n_per_category,
            seed=args.seed,
            chain_length=args.chain_length,
        )
    records = [
        synthetic_record_from_chain(chain, index=index, seed=args.seed)
        for index, chain in enumerate(chains)
    ]
    if args.dry_run:
        preview = [
            {
                "trace_id": record["trace_id"],
                "category": record["category"],
                "reflection_categories": record["reflection_categories"],
            }
            for record in records[:3]
        ]
        print(
            {
                "dry_run": True,
                "mode": "synthetic_balanced",
                "records": len(records),
                "output": str(args.output),
                "preview": preview,
            }
        )
        return records

    write_synthetic_records(records, args.output)
    print(f"Wrote {len(records)} synthetic traces to {args.output}")
    return records


def generate_trace(
    question: str,
    prompt_template: str,
    tokenizer: AutoTokenizer,
    model: AutoModelForCausalLM,
    args: argparse.Namespace,
) -> str:
    import torch

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
    if args.taxonomy:
        annotate_taxonomy(args.taxonomy_input, args.output, dry_run=args.dry_run)
        return

    if args.synthetic_balanced:
        generate_synthetic_balanced(args)
        return

    if args.dry_run:
        print(
            {
                "dry_run": True,
                "mode": "generate",
                "model_name_or_path": args.model_name_or_path,
                "split": args.split,
                "max_samples": args.max_samples,
                "output": str(args.output),
            }
        )
        return

    if not args.model_name_or_path:
        raise ValueError("--model-name-or-path is required unless --taxonomy or --dry-run is set.")

    import torch
    from datasets import load_dataset
    from transformers import AutoModelForCausalLM, AutoTokenizer, set_seed

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

    with args.output.open("w", encoding="utf-8") as handle:
        for idx, sample in enumerate(dataset):
            reasoning_trace = generate_trace(
                sample["question"],
                prompt_template,
                tokenizer,
                model,
                args,
            )
            final_answer = extract_final_answer(reasoning_trace)
            record = {
                "sample_id": f"gsm8k-{args.split}-{idx}",
                "task_id": f"gsm8k-{args.split}-{idx}",
                "task_type": "gsm8k",
                "question": sample["question"],
                "reasoning_trace": reasoning_trace,
                "reflection_spans": extract_reflection_spans(reasoning_trace, tokenizer),
                "final_answer": final_answer,
                "reference_answer": sample["answer"],
                "correctness": is_correct(final_answer, sample["answer"]),
                "model_name": args.model_name_or_path,
                "generation_config": generation_config,
            }
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

    print(f"Wrote {len(dataset)} traces to {args.output}")


if __name__ == "__main__":
    main()
