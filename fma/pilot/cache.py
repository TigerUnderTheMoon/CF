"""SQLite-backed cache for pilot LLM API calls."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


@dataclass(frozen=True)
class CacheEntry:
    raw_output: str
    metadata: dict[str, Any]
    cost_usd: float


class APICache:
    """Persist prompt/model/sampling keyed API responses on disk."""

    def __init__(self, path: str | Path = "outputs/cache/llm_api_cache.sqlite", *, enabled: bool = True) -> None:
        self.path = Path(path)
        self.enabled = enabled
        self._lock = threading.Lock()
        if self.enabled:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self._ensure_schema()

    def get(
        self,
        *,
        prompt: str,
        model_name: str,
        temperature: float,
        seed: int | None,
        top_p: float,
    ) -> CacheEntry | None:
        if not self.enabled:
            return None
        key = cache_key(
            prompt=prompt,
            model_name=model_name,
            temperature=temperature,
            seed=seed,
            top_p=top_p,
        )
        with self._connect() as conn:
            row = conn.execute(
                "select raw_output, metadata_json, cost_usd from api_cache where cache_key = ?",
                (key,),
            ).fetchone()
        if row is None:
            return None
        return CacheEntry(
            raw_output=str(row[0]),
            metadata=json.loads(row[1]),
            cost_usd=float(row[2]),
        )

    def set(
        self,
        *,
        prompt: str,
        model_name: str,
        temperature: float,
        seed: int | None,
        top_p: float,
        raw_output: str,
        metadata: Mapping[str, Any],
        cost_usd: float,
    ) -> None:
        if not self.enabled:
            return
        key = cache_key(
            prompt=prompt,
            model_name=model_name,
            temperature=temperature,
            seed=seed,
            top_p=top_p,
        )
        payload = json.dumps(dict(metadata), ensure_ascii=True, sort_keys=True)
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                insert or replace into api_cache (
                    cache_key, prompt_sha256, model_name, temperature, seed, top_p,
                    raw_output, metadata_json, cost_usd, created_at
                )
                values (?, ?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
                """,
                (
                    key,
                    prompt_sha256(prompt),
                    model_name,
                    float(temperature),
                    seed,
                    float(top_p),
                    raw_output,
                    payload,
                    float(cost_usd),
                ),
            )

    def _ensure_schema(self) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """
                create table if not exists api_cache (
                    cache_key text primary key,
                    prompt_sha256 text not null,
                    model_name text not null,
                    temperature real not null,
                    seed integer,
                    top_p real not null,
                    raw_output text not null,
                    metadata_json text not null,
                    cost_usd real not null,
                    created_at text not null
                )
                """
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path)


def prompt_sha256(prompt: str) -> str:
    return hashlib.sha256(prompt.encode("utf-8")).hexdigest()


def cache_key(
    *,
    prompt: str,
    model_name: str,
    temperature: float,
    seed: int | None,
    top_p: float,
) -> str:
    payload = {
        "prompt_sha256": prompt_sha256(prompt),
        "model_name": model_name,
        "temperature": float(temperature),
        "seed": seed,
        "top_p": float(top_p),
    }
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=True, sort_keys=True).encode("utf-8")
    ).hexdigest()


__all__ = ["APICache", "CacheEntry", "cache_key", "prompt_sha256"]
