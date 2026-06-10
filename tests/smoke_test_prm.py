"""Minimal PRM model smoke test.

Tests perplexity-based PRM proxy inference on a single trace.
"""

import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from fma.prm.perplexity_prm import PerplexityPRMScorer  # noqa: E402

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("prm_smoke")


def main() -> None:
    try:
        scorer = PerplexityPRMScorer(
            model_name="Qwen2.5-0.5B-Instruct",
            device="cpu",
        )
    except ImportError as e:
        logger.info("SKIP: dependencies not available: %s", e)
        return
    except Exception as e:
        logger.error("FAIL: model loading: %s", e)
        return

    question = (
        "If Janet's ducks lay 16 eggs per day and she eats 3, "
        "how many does she have left?"
    )
    steps = [
        "Janet's ducks lay 16 eggs per day.",
        "She eats 3 for breakfast every morning.",
        "16 - 3 = 13 eggs remaining.",
    ]

    try:
        scores = scorer.score_steps(question, steps)
    except Exception as e:
        logger.error("FAIL: inference: %s", repr(e))
        return

    logger.info("PRM step scores: %s", scores)

    if any(abs(s - 0.5) > 0.01 for s in scores):
        logger.info("PASS: Got discriminative PRM scores")
    else:
        logger.warning("WARN: All scores are near 0.5 (non-discriminative)")


if __name__ == "__main__":
    main()
