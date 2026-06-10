"""Generate HotpotQA reasoning traces with reflection tags via DeepSeek API.

Usage:
  python scripts/generate_hotpotqa_traces.py --max-samples 500 --workers 8
  python scripts/generate_hotpotqa_traces.py --smoke-test
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import logging  # noqa: E402

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(message)s",
)
logger = logging.getLogger("hotpotqa_gen")

DEFAULT_PROMPT_PATH = PROJECT_ROOT / "prompts" / "real_task_reflection_generation.txt"
DEFAULT_SOURCE_PATH = PROJECT_ROOT / "data" / "real_task_pilot" / "hotpotqa_validation.jsonl"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "outputs" / "hotpotqa_traces"
DEFAULT_API_KEY = os.environ.get("OPENAI_API_KEY", "")
DEFAULT_BASE_URL = "https://api.deepseek.com/v1/chat/completions"
DEFAULT_MODEL = "deepseek-chat"


def parse_args() -> argparse.Namespace:
    import argparse

    parser = argparse.ArgumentParser(
        description="Generate HotpotQA traces with DeepSeek API"
    )
    parser.add_argument("--max-samples", type=int, default=500)
    parser.add_argument("--workers", type=int, default=8)
    parser.add_argument("--smoke-test", action="store_true", help="Generate 3 traces only")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE_PATH)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--prompt", type=Path, default=DEFAULT_PROMPT_PATH)
    parser.add_argument("--api-key", type=str, default=DEFAULT_API_KEY)
    parser.add_argument("--base-url", type=str, default=DEFAULT_BASE_URL)
    parser.add_argument("--model", type=str, default=DEFAULT_MODEL)
    parser.add_argument("--temperature", type=float, default=0.2)
    parser.add_argument("--max-tokens", type=int, default=600)
    return parser.parse_args()


def load_questions(source_path: Path, max_samples: int) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with source_path.open("r", encoding="utf-8") as handle:
        for line in handle:
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError:
                continue
            if 0 < max_samples <= len(rows):
                break
    return rows


def build_prompt(prompt_template: str, question: str, task_type: str = "hotpotqa") -> str:
    return prompt_template.format(question=question, task_type=task_type)


def call_api(
    prompt: str,
    api_key: str,
    base_url: str,
    model: str,
    temperature: float,
    max_tokens: int,
) -> dict[str, Any]:
    payload = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "response_format": {"type": "json_object"},
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        base_url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            body = json.loads(resp.read())
            content = body["choices"][0]["message"]["content"]
            try:
                parsed = json.loads(content)
            except json.JSONDecodeError:
                parsed = {"observable_trace": content, "final_answer": ""}
            return {
                "status": "ok",
                "final_answer": str(parsed.get("final_answer", "")),
                "observable_trace": str(parsed.get("observable_trace", content)),
                "usage": body.get("usage", {}),
                "model": body.get("model", model),
            }
    except Exception as exc:
        return {"status": "error", "error": str(exc)}


def generate_one(
    args: argparse.Namespace,
    row: dict[str, Any],
    prompt_template: str,
    index: int,
) -> dict[str, Any]:
    question = str(row.get("question", ""))
    prompt = build_prompt(prompt_template, question)

    result = call_api(
        prompt=prompt,
        api_key=args.api_key,
        base_url=args.base_url,
        model=args.model,
        temperature=args.temperature,
        max_tokens=args.max_tokens,
    )

    return {
        "index": index,
        "question": question,
        "reference_answer": str(row.get("reference_answer", "")),
        "aliases": row.get("aliases", []),
        "task_type": "hotpotqa",
        "source_dataset": row.get("source_dataset", "hotpot_qa"),
        "final_answer": result.get("final_answer", ""),
        "observable_trace": result.get("observable_trace", ""),
        "model_name": result.get("model", args.model),
        "api_usage": result.get("usage", {}),
        "api_status": result.get("status", "error"),
        "api_error": result.get("error", ""),
    }


def run(args: argparse.Namespace) -> dict[str, Any]:
    if args.smoke_test:
        args.max_samples = 3
        args.workers = 1

    if not args.api_key:
        logger.error("No API key provided.")
        raise ValueError("Set OPENAI_API_KEY or pass --api-key")

    logger.info("Loading questions from %s", str(args.source))
    questions = load_questions(args.source, args.max_samples)
    logger.info("Questions loaded: %d", len(questions))

    prompt_template = args.prompt.read_text(encoding="utf-8")
    args.output_dir.mkdir(parents=True, exist_ok=True)

    t0 = time.time()
    results: list[dict[str, Any]] = []
    errors = 0

    with ThreadPoolExecutor(max_workers=args.workers) as executor:
        futures = {
            executor.submit(generate_one, args, row, prompt_template, i): i
            for i, row in enumerate(questions)
        }
        for future in as_completed(futures):
            idx = futures[future]
            try:
                result = future.result()
                results.append(result)
                status = result.get("api_status", "?")
                if status == "error":
                    errors += 1
                if idx % 10 == 0:
                    print(f"[{len(results)}/{len(questions)}] errors={errors}")
            except Exception as exc:
                logger.error("Worker %d failed: %s", idx, str(exc))
                errors += 1

    elapsed = time.time() - t0
    results.sort(key=lambda r: r["index"])

    output_path = args.output_dir / "generated_traces.jsonl"
    with output_path.open("w", encoding="utf-8") as handle:
        for r in results:
            handle.write(json.dumps(r, ensure_ascii=False) + "\n")

    successful = sum(1 for r in results if r["api_status"] == "ok")
    meta = {
        "total": len(questions),
        "successful": successful,
        "errors": errors,
        "elapsed_seconds": round(elapsed, 1),
        "model": args.model,
        "base_url": args.base_url,
    }
    meta_path = args.output_dir / "generation_meta.json"
    with meta_path.open("w", encoding="utf-8") as handle:
        json.dump(meta, handle, indent=2)

    logger.info(
        "Generation complete: total=%d success=%d errors=%d elapsed=%.1fs",
        meta["total"], meta["successful"], meta["errors"], meta["elapsed_seconds"],
    )
    return meta


if __name__ == "__main__":
    import argparse

    args = parse_args()
    run(args)
