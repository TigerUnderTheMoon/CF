"""Counterfactual replay utilities."""

from fma.replay.counterfactual import (
    ReplayConfig,
    detect_reflection_spans,
    mask_reflection_content_ids,
    replay_record,
    resolve_mask_token_id,
)

__all__ = [
    "ReplayConfig",
    "detect_reflection_spans",
    "mask_reflection_content_ids",
    "replay_record",
    "resolve_mask_token_id",
]
