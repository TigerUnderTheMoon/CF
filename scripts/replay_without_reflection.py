"""CLI for deterministic replay after length-preserving reflection masking."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import jsonlines
import torch
from transformers import AutoModelForCausalLM, AutoTokenizer, set_seed

from fma.replay.counterfactual import ReplayConfig, replay_record


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Deterministically replay reflection traces with reflection content masked."
    )
    parser.add_argument(
        "--input",
        type=Path,
        default=Path("outputs") / "reflection_traces" / "gsm8k_reflection_traces.jsonl",
        help="Input JSONL produced by generate_reflection_traces.py.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("outputs") / "counterfactual_results.jsonl",
    )
    parser.add_argument(
        "--model-name-or-path",
        default=None,
        help="Local path or HF model id. Defaults to the first input record's model_name.",
    )
    parser.add_argument("--max-input-tokens", type=int, default=2048)
    parser.add_argument("--max-new-tokens", type=int, default=512)
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
        default=PROJECT_ROOT / "prompts" / "reflection_generation.txt",
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


def load_model_and_tokenizer(
    model_name_or_path: str,
    torch_dtype: str,
    device_map: str | None,
    trust_remote_code: bool,
) -> tuple[AutoTokenizer, AutoModelForCausalLM]:
    tokenizer = AutoTokenizer.from_pretrained(
        model_name_or_path,
        trust_remote_code=trust_remote_code,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    model = AutoModelForCausalLM.from_pretrained(
        model_name_or_path,
        torch_dtype=resolve_dtype(torch_dtype),
        device_map=device_map,
        trust_remote_code=trust_remote_code,
    )
    if device_map is None:
        device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        model.to(device)
    model.eval()
    return tokenizer, model


def infer_model_name(records: list[dict[str, Any]], requested_model: str | None) -> str:
    if requested_model:
        return requested_model
    if not records:
        raise ValueError("Input JSONL is empty; cannot infer model_name.")
    model_name = records[0].get("model_name")
    if not model_name:
        raise ValueError("Pass --model-name-or-path because input records lack model_name.")
    return model_name


def main() -> None:
    args = parse_args()
    set_seed(args.seed)

    with jsonlines.open(args.input, mode="r") as reader:
        records = list(reader)

    model_name_or_path = infer_model_name(records, args.model_name_or_path)
    prompt_template = args.prompt_file.read_text(encoding="utf-8")
    tokenizer, model = load_model_and_tokenizer(
        model_name_or_path,
        args.torch_dtype,
        args.device_map,
        args.trust_remote_code,
    )
    replay_config = ReplayConfig(
        max_input_tokens=args.max_input_tokens,
        max_new_tokens=args.max_new_tokens,
        seed=args.seed,
        model_name_or_path=model_name_or_path,
    )

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with jsonlines.open(args.output, mode="w") as writer:
        for record in records:
            writer.write(replay_record(record, prompt_template, tokenizer, model, replay_config))

    print(f"Wrote {len(records)} counterfactual replay results to {args.output}")


if __name__ == "__main__":
    main()
