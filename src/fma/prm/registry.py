"""Registry of known public Process Reward Models."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType


@dataclass(frozen=True)
class PRMModelSpec:
    model_name: str
    hf_id: str
    model_type: str
    input_format: str
    score_per: str
    max_seq_length: int = 2048
    requires_special_tokens: bool = False
    step_separator: str = "\n"


KNOWN_PRM_MODELS: MappingProxyType[str, PRMModelSpec] = MappingProxyType(
    {
        "Qwen2.5-Math-PRM": PRMModelSpec(
            model_name="Qwen2.5-Math-PRM",
            hf_id="Qwen/Qwen2.5-Math-PRM7B",
            model_type="reward_model",
            input_format="math_chain",
            score_per="step",
            max_seq_length=4096,
            requires_special_tokens=True,
            step_separator=" kb ",
        ),
        "Qwen2.5-Math-PRM-1.5B": PRMModelSpec(
            model_name="Qwen2.5-Math-PRM-1.5B",
            hf_id="Qwen/Qwen2.5-Math-PRM1.5B",
            model_type="reward_model",
            input_format="math_chain",
            score_per="step",
            max_seq_length=4096,
            requires_special_tokens=True,
            step_separator=" kb ",
        ),
        "Math-Shepherd": PRMModelSpec(
            model_name="Math-Shepherd",
            hf_id="MathShepherd/math-shepherd-mistral-7b-rl",
            model_type="process_reward",
            input_format="step_separated",
            score_per="step",
            max_seq_length=2048,
            step_separator=" ki ",
        ),
        "RLVR-PRM": PRMModelSpec(
            model_name="RLVR-PRM",
            hf_id="rlvr/rlvr-prm",
            model_type="process_reward",
            input_format="chain",
            score_per="token_pair",
            max_seq_length=4096,
        ),
        "Skywork-Reward-8B": PRMModelSpec(
            model_name="Skywork-Reward-8B",
            hf_id="Skywork/Skywork-Reward-Llama-3.1-8B",
            model_type="reward_model",
            input_format="qa_pair",
            score_per="completion",
            max_seq_length=2048,
            requires_special_tokens=False,
            step_separator=" ",
        ),
    }
)


def list_prm_models() -> dict[str, str]:
    """Return available PRM model names with their HuggingFace IDs."""
    return {name: spec.hf_id for name, spec in KNOWN_PRM_MODELS.items()}


def get_prm_spec(model_name: str) -> PRMModelSpec:
    """Look up a PRM model specification by name."""
    if model_name not in KNOWN_PRM_MODELS:
        available = ", ".join(sorted(KNOWN_PRM_MODELS))
        raise ValueError(f"Unknown PRM model {model_name!r}. Available: {available}")
    return KNOWN_PRM_MODELS[model_name]


__all__ = ["KNOWN_PRM_MODELS", "PRMModelSpec", "get_prm_spec", "list_prm_models"]
