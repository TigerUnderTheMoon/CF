from __future__ import annotations

from fma.taxonomy import ReflectionTaxonomizer
from fma.types import ReflectionCategory, ReflectionTrace


def make_trace(text: str) -> ReflectionTrace:
    return ReflectionTrace(
        trace_id="trace_1",
        reflection_text=text,
        task_id="task_1",
        task_difficulty=3,
        intervention_magnitude=0.5,
        locality_score=0.9,
    )


def test_classify_deterministic() -> None:
    taxonomizer = ReflectionTaxonomizer()
    trace = make_trace("Let me verify the answer and check the arithmetic.")
    first = taxonomizer.classify(trace)
    for _ in range(100):
        assert taxonomizer.classify(trace) == first


def test_empty_trace_fallback() -> None:
    annotation = ReflectionTaxonomizer().classify(make_trace("   "))
    assert annotation.category is ReflectionCategory.OTHER
    assert annotation.confidence == 0.0
    assert annotation.rationale == "empty trace"


def test_tie_breaking() -> None:
    taxonomizer = ReflectionTaxonomizer(
        {
            "DECOMPOSITION": ["alpha"],
            "VERIFICATION": ["alpha"],
        }
    )
    annotation = taxonomizer.classify(make_trace("alpha"))
    assert annotation.category is ReflectionCategory.DECOMPOSITION
    assert annotation.confidence == 1.0


def test_confidence_bounds() -> None:
    taxonomizer = ReflectionTaxonomizer()
    texts = [
        "verify the result",
        "not sure about this",
        "remember the formula",
        "no matching functional cue",
    ]
    for text in texts:
        confidence = taxonomizer.classify(make_trace(text)).confidence
        assert 0.0 <= confidence <= 1.0


def test_custom_keywords() -> None:
    taxonomizer = ReflectionTaxonomizer({"RETRIEVAL": ["fetch datum"]})
    annotation = taxonomizer.classify(make_trace("I should fetch datum from memory."))
    assert annotation.category is ReflectionCategory.RETRIEVAL
    assert annotation.confidence == 1.0


def test_all_categories_reachable() -> None:
    taxonomizer = ReflectionTaxonomizer()
    examples = {
        ReflectionCategory.DECOMPOSITION: "break down the task",
        ReflectionCategory.VERIFICATION: "verify the total",
        ReflectionCategory.ERROR_CORRECTION: "correct the mistake",
        ReflectionCategory.BACKTRACKING: "backtrack to an alternative path",
        ReflectionCategory.UNCERTAINTY_MONITORING: "I am uncertain and not sure",
        ReflectionCategory.PLANNING: "plan the next step",
        ReflectionCategory.CONSTRAINT_TRACKING: "track the constraint boundary",
        ReflectionCategory.RETRIEVAL: "recall and remember the rule",
        ReflectionCategory.OTHER: "plain text without taxonomy cues",
    }
    for category, text in examples.items():
        assert taxonomizer.classify(make_trace(text)).category is category
