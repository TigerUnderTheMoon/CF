# AGENTS.md — Functional Metacognitive Attribution (FMA)

## 1. Project Goal

Study the functional organization of reflective cognition via intervention-based attribution in reflective language agents.

The repository focuses on:

- metacognitive operations
- structure-preserving intervention
- local functional utility estimation
- attribution-aware process supervision

The project MUST NOT be framed as:

- full causal identification
- generic PRM tuning
- token attribution
- heuristic reflection scoring

Correct framing:

> intervention-based functional attribution for reflective cognition dynamics.

---

## 2. Code Architecture

Implementation lives under `src/fma/`. The import path is `fma.*` (configured via `pyproject.toml: packages = [{include = "fma", from = "src"}]`).

> **Convention**: Throughout this document, file system paths use the `src/fma/...` prefix. Import paths use `fma.*`.

### 2.1 Implemented Modules

| Theory Component | File System Path | Import Path | Responsibility |
|---|---|---|---|
| Reflection Extraction | `src/fma/taxonomy/`, `src/fma/real_task_pilot/parsing.py` | `fma.taxonomy`, `fma.real_task_pilot.parsing` | observable span and taxonomy extraction |
| Structure-Preserving Intervention | `src/fma/intervention/`, `src/fma/replay/` | `fma.intervention`, `fma.replay` | masking, replacement, replay helpers |
| Reflection Graph | `src/fma/graph/` | `fma.graph` | structural graph construction, motif analysis, diagnostics |
| CIU Estimation | `src/fma/ciu/` | `fma.ciu` | local interventional utility estimation (simple outcome difference) |
| Attribution Engine | `src/fma/attribution/` | `fma.attribution` | attribution result container + IncrementalAttributionEngine, ParallelAttributionEngine |
| Pilot / Validation | `src/fma/pilot/`, `src/fma/real_task_pilot/` | `fma.pilot`, `fma.real_task_pilot` | API client, audit, caching, resilience, v2/v2.1/v2.2/v3 validation pipeline |
| Evaluation | `src/fma/eval/` | `fma.eval` | attribution metrics, stratified eval, structural validation, redundancy, locality, stability |
| Visualization | `src/fma/visualization/` | `fma.visualization` | plots, DAGs, intervention traces |
| Generation | `src/fma/generation/` | `fma.generation` | diverse reflection generation, template pools |
| FMA Aggregation | `src/fma/fma/` | `fma.fma` | distribution-conditioned CIU aggregation (simplified; no temperature-based softmax weights) |
| Counterfactual Replay | `src/fma/replay/` | `fma.replay` | counterfactual replay with masked reflection |
| Open-source Data Ingestion | `src/fma/data/` | `fma.data` | PRM800K, ProcessBench, GSM8K CoT loader + step parsing + taxonomy classification |
| Frozen PRM Scoring | `src/fma/prm/` | `fma.prm` | frozen public PRM inference wrapper (Qwen2.5-Math-PRM, Math-Shepherd, RLVR-PRM) |
| Downstream Comparison | `src/fma/utility/` | `fma.utility` | filtering A/B experiment, FMA vs PRM vs baseline comparison, reporting |
| Utils | `src/fma/utils/` | `fma.utils` | config loading, logging, benchmarking, cleanup |

### 2.2 Planned Modules (NOT YET IMPLEMENTED)

The following modules are described in Sections 3-4 as design targets. No implementation code exists. They MUST NOT be described as completed evidence.

| Planned Component | Target Path | Note |
|---|---|---|
| Conditional Intervention Distribution | `src/fma/conditional/` | No files. Current replacement uses random template swap. |
| Counterfactual Matching | `src/fma/matching/` | No files. Algorithm template in Section 4.2 only. |
| Doubly Robust Estimation | `src/fma/dr/` | No files. Algorithm template in Section 4.3 only. |
| Attribution Computation | `src/fma/attribution/__init__.py` | `compute_attribution()` removed (was NotImplementedError). Engine classes are implemented. |
| Diagnostic Summarization | `src/fma/diagnostics/__init__.py` | `summarize_diagnostics()` removed (was NotImplementedError). DiagnosticResult dataclass retained. |

### 2.3 Actual Running Pipeline

The operational pipeline uses deterministic scripts, not the ABC interface architecture:

- **Phase 5**: `scripts/run_counterfactual_attribution.py` -> `fma/eval/counterfactual_attribution.py`
- **Phase 6**: `scripts/run_structural_attribution.py` -> `fma/graph/` modules
- **Phase 7**: `scripts/run_redundancy_analysis.py` -> `fma/eval/redundancy/` modules
- **Real-task pilot**: `scripts/run_real_task_pilot.py` -> `fma/real_task_pilot/` modules
- **Fresh holdout**: `scripts/s_fma_v2_*.py`, `scripts/run_real_task_v3_smoke.py` etc.

### 2.4 Gap: Planned vs Implemented

| Interface or Feature | AGENTS.md Status | Actual Status |
|---|---|---|
| `Intervention` ABC (masking, replacement, perturbation) | 3 subclasses defined | Only masking fully implemented (`replay/counterfactual.py`). Replacement uses random category swap (`intervention/structural_interventions.py`). Perturbation has `_contradict()` only. |
| `ConditionalDistribution.sample()` | ABC defined | **Not implemented.** No `fma/conditional/` directory. Current replacement uses template pool, not conditional sampling. |
| `UtilityEstimator.estimate()` | ABC defined | **Not implemented.** CIU uses `ciu/estimator.py` with simple outcome difference, not the ABC pattern. |
| `Matcher.match()` | ABC defined | **Not implemented.** No `fma/matching/` directory. No counterfactual matching in the pipeline. |
| `DoublyRobustEstimator.estimate()` | ABC defined | **Not implemented.** No `fma/dr/` directory. All CIU estimates are raw differences, not DR-corrected. |
| `FMAAggregator.aggregate()` | ABC defined | Partially implemented. `fma/fma/aggregator.py` does group-mean aggregation, lacks temperature-based softmax weights. |
| Data scale | 800 traces / 2400 reflective steps | Synthetic-only. Real-task validation: **all 6 routes failed** (v2, v2.1, v2.2, v3, v3.1). External validity limited to synthetic data. |
| Open-source data ingestion | Planned (no files) | **Implemented.** `src/fma/data/` loads PRM800K, ProcessBench, GSM8K CoT, normalizes to internal format. |
| Frozen PRM scoring | Planned (no files) | **Implemented.** `src/fma/prm/` wraps Qwen2.5-Math-PRM, Math-Shepherd, RLVR-PRM (frozen inference only). |
| Downstream comparison | Planned (no files) | **Implemented.** `src/fma/utility/` provides filtering A/B experiment, FMA vs PRM vs heuristic comparison report. |
| CIU three-value restriction | CIU restricted to {-1, 0, 1} | **Lifted.** `ciu/estimator.py` now accepts continuous CIU in [-1, 1]. |
| CoT step parsing | Only `<reflection>` XML | **Extended.** `parsing.py` has `parse_cot_steps()` for free-text CoT segmentation. |

---

## 3. Core Implementation Contracts

The following abstract interface contracts define the **planned target architecture**. They are NOT all currently implemented — see Section 2.4 for the gap analysis. Implementations SHOULD follow these contracts when built, but existing working code (Phase 5-7 pipeline scripts) takes precedence over unimplemented ABCs.

### 3.1 Data Structures

```python
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Callable
import numpy as np

@dataclass
class ReasoningStep:
    text: str
    step_type: str  # "reasoning" | "metacognition" | "action" | "observation"
    step_idx: int

@dataclass
class Trajectory:
    steps: List[ReasoningStep]
    task_id: str
    task_type: str  # e.g., "gsm8k", "math", "hotpotqa", "swe-bench-lite"

@dataclass
class MetacognitiveSpan:
    start_idx: int
    end_idx: int
    content: str
    operation_type: str  # "self-reflection" | "self-evaluation" | "error_diagnosis" | "plan_revision" | "strategy_critique"

@dataclass
class InterventionResult:
    trajectory: Trajectory
    intervention_type: str
    original_span: MetacognitiveSpan
    modified_span: Optional[MetacognitiveSpan]

@dataclass
class CIUResult:
    context: List[ReasoningStep]
    span: MetacognitiveSpan
    ciu_score: float
    original_outcome: float
    intervened_outcome: float

@dataclass
class FMAResult:
    span_type: str
    fma_score: float
    task_distribution: str
    sample_count: int
```

### 3.2 Intervention Interface

```python
from abc import ABC, abstractmethod

class Intervention(ABC):
    @abstractmethod
    def intervene(
        self,
        trajectory: Trajectory,
        span: MetacognitiveSpan,
    ) -> InterventionResult:
        """
        Apply structure-preserving intervention.

        MUST preserve:
        - token count (via masking or length-matched replacement)
        - positional structure (span start/end indices unchanged)
        - autoregressive consistency (no structural layout change)
        """
        pass

class MaskingIntervention(Intervention):
    """Replace span content with [REASONING_MASK] tokens preserving length."""
    pass

class ReplacementIntervention(Intervention):
    """Sample replacement from ConditionalDistribution preserving length."""
    pass

class PerturbationIntervention(Intervention):
    """Apply paraphrase/compression/contradiction with Sim > delta."""
    pass
```

### 3.3 Conditional Distribution Interface

```python
from abc import ABC, abstractmethod

class ConditionalDistribution(ABC):
    @abstractmethod
    def sample(
        self,
        context: List[ReasoningStep],
        original_span: MetacognitiveSpan,
    ) -> MetacognitiveSpan:
        """
        Sample semantically compatible replacement.

        Constraints:
        - same task category as original trajectory
        - same reasoning stage (relative position)
        - similar semantic intent (embedding cosine similarity > 0.7)
        - similar token budget (length difference < 20%)
        """
        pass
```

### 3.4 Utility Estimator Interface

```python
from abc import ABC, abstractmethod

class UtilityEstimator(ABC):
    @abstractmethod
    def estimate(
        self,
        original_result: InterventionResult,
        intervened_result: InterventionResult,
        evaluator: Callable[[Trajectory], float],
    ) -> float:
        """
        Estimate local functional utility (CIU).

        Returns: outcome difference (original - intervened)
        """
        pass
```

### 3.5 Matching Interface

```python
from abc import ABC, abstractmethod

class Matcher(ABC):
    @abstractmethod
    def match(
        self,
        treated_pool: List[Dict[str, Any]],
        control_pool: List[Dict[str, Any]],
    ) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]:
        """
        Construct matched intervention pairs.

        Rules:
        - 1:1 matching without replacement
        - normalized Euclidean distance on matching features
        - discard unmatched samples
        """
        pass
```

### 3.6 DR Estimator Interface

```python
from abc import ABC, abstractmethod

class DoublyRobustEstimator(ABC):
    @abstractmethod
    def estimate(
        self,
        contexts: np.ndarray,
        outcomes: np.ndarray,
        interventions: np.ndarray,
        outcome_model: Any,
        propensity_model: Any,
    ) -> np.ndarray:
        """
        Estimate intervention-conditioned utility via DR correction.

        interventions: binary array T_k in {0, 1}
        """
        pass
```

### 3.7 FMA Aggregator Interface

```python
from abc import ABC, abstractmethod

class FMAAggregator(ABC):
    @abstractmethod
    def aggregate(
        self,
        ciu_scores: List[CIUResult],
        task_distribution: str,
    ) -> List[FMAResult]:
        """
        Aggregate CIU under task distribution D.

        FMA is distribution-dependent and task-conditioned.
        """
        pass
```

---

## 4. Algorithm Templates

### 4.1 CIU Estimation (Executable Template)

```python
# fma/ciu/estimator.py
from typing import Callable

def estimate_ciu(
    trajectory: Trajectory,
    span: MetacognitiveSpan,
    intervention: Intervention,
    evaluator: Callable[[Trajectory], float],
) -> CIUResult:
    """
    Estimate Conditional Interventional Utility.

    CIU(m_k | x_<k) = E[Y | do(m_k), x_<k] - E[Y | do(empty), x_<k]
    """
    # Step 1: Evaluate original trajectory outcome
    original_outcome = evaluator(trajectory)

    # Step 2: Apply structure-preserving intervention
    intervened = intervention.intervene(trajectory, span)

    # Step 3: Evaluate intervened trajectory outcome
    intervened_outcome = evaluator(intervened.trajectory)

    # Step 4: Compute outcome difference
    ciu_score = original_outcome - intervened_outcome

    context = trajectory.steps[:span.start_idx]

    return CIUResult(
        context=context,
        span=span,
        ciu_score=ciu_score,
        original_outcome=original_outcome,
        intervened_outcome=intervened_outcome,
    )
```

### 4.2 Counterfactual Matching (Executable Template)

```python
# planned module: fma/matching/matcher.py
import numpy as np
from typing import List, Dict, Any, Tuple
from sklearn.preprocessing import StandardScaler

MATCHING_FEATURES = [
    "trajectory_length",
    "token_budget",
    "task_difficulty",
    "reasoning_depth",
    "reflection_density",
    "step_index",
]

def extract_matching_features(
    trajectory: Trajectory,
    span: MetacognitiveSpan,
) -> np.ndarray:
    """
    Extract and normalize matching feature vector φ(x).

    Features:
    - trajectory_length: total steps in trajectory
    - token_budget: total token count
    - task_difficulty: normalized difficulty score (0-1)
    - reasoning_depth: max nesting depth of reasoning
    - reflection_density: metacognitive spans / total steps
    - step_index: relative position of span in trajectory (0-1)
    """
    features = np.array([
        len(trajectory.steps),
        sum(len(s.text.split()) for s in trajectory.steps),
        get_task_difficulty(trajectory.task_type),  # user-defined
        compute_reasoning_depth(trajectory.steps),    # user-defined
        count_metacognitive_spans(trajectory.steps) / len(trajectory.steps),
        span.start_idx / len(trajectory.steps),
    ])
    return features

def match_counterfactual_pairs(
    treated_pool: List[Dict[str, Any]],
    control_pool: List[Dict[str, Any]],
) -> List[Tuple[Dict[str, Any], Dict[str, Any]]]:
    """
    1:1 nearest neighbor matching without replacement.

    Args:
        treated_pool: list of dicts with key "features" (np.ndarray)
        control_pool: list of dicts with key "features" (np.ndarray)

    Returns:
        List of (treated, control) matched pairs
    """
    if len(treated_pool) == 0 or len(control_pool) == 0:
        return []

    # Normalize features
    scaler = StandardScaler()
    treated_features = np.array([t["features"] for t in treated_pool])
    control_features = np.array([c["features"] for c in control_pool])
    all_features = np.vstack([treated_features, control_features])
    scaler.fit(all_features)

    treated_norm = scaler.transform(treated_features)
    control_norm = scaler.transform(control_features)

    # Greedy 1:1 matching without replacement
    matched_pairs = []
    used_control = set()

    for i, t_feat in enumerate(treated_norm):
        distances = np.linalg.norm(control_norm - t_feat, axis=1)
        for j in np.argsort(distances):
            if j not in used_control:
                matched_pairs.append((treated_pool[i], control_pool[j]))
                used_control.add(j)
                break

    return matched_pairs

def get_task_difficulty(task_type: str) -> float:
    """Return normalized difficulty score."""
    difficulty_map = {
        "gsm8k": 0.3,
        "math": 0.7,
        "hotpotqa": 0.5,
        "swe-bench-lite": 0.8,
    }
    return difficulty_map.get(task_type, 0.5)

def compute_reasoning_depth(steps: List[ReasoningStep]) -> int:
    """Compute maximum reasoning nesting depth."""
    # Placeholder: actual implementation depends on parsing logic
    return 1

def count_metacognitive_spans(steps: List[ReasoningStep]) -> int:
    """Count metacognitive steps in trajectory."""
    return sum(1 for s in steps if s.step_type == "metacognition")
```

### 4.3 Doubly Robust Estimation (Executable Template)

```python
# planned module: fma/dr/estimator.py
import numpy as np
from typing import Any

def doubly_robust_estimate(
    context_features: np.ndarray,
    treatment: int,
    outcome: float,
    outcome_model: Any,
    propensity_model: Any,
    clip_bound: float = 0.01,
) -> float:
    """
    DR estimator for functional utility.

    U_DR = m(x,1) - m(x,0) + T*(Y - m(x,1))/e(x) - (1-T)*(Y - m(x,0))/(1-e(x))

    Args:
        context_features: feature vector φ(x_<k)
        treatment: T_k in {0, 1}
        outcome: Y (task success indicator or normalized score)
        outcome_model: fitted model with predict(features, treatment) method
        propensity_model: fitted model with predict_proba(features) method
        clip_bound: minimum propensity score to avoid division by zero

    Returns:
        DR-corrected utility estimate
    """
    # Predict potential outcomes
    m1 = outcome_model.predict(context_features.reshape(1, -1), treatment=1)[0]
    m0 = outcome_model.predict(context_features.reshape(1, -1), treatment=0)[0]

    # Predict propensity score with clipping
    e = propensity_model.predict_proba(context_features.reshape(1, -1))[0][1]
    e = np.clip(e, clip_bound, 1.0 - clip_bound)

    # DR correction
    if treatment == 1:
        dr_estimate = (m1 - m0) + (outcome - m1) / e
    else:
        dr_estimate = (m1 - m0) - (outcome - m0) / (1.0 - e)

    return float(dr_estimate)

def batch_doubly_robust_estimate(
    contexts: np.ndarray,
    treatments: np.ndarray,
    outcomes: np.ndarray,
    outcome_model: Any,
    propensity_model: Any,
    clip_bound: float = 0.01,
) -> np.ndarray:
    """
    Batch DR estimation for multiple samples.

    Args:
        contexts: (n_samples, n_features) array
        treatments: (n_samples,) binary array
        outcomes: (n_samples,) outcome array

    Returns:
        (n_samples,) array of DR estimates
    """
    n_samples = len(treatments)
    dr_estimates = np.zeros(n_samples)

    # Batch predict
    m1_all = outcome_model.predict(contexts, treatment=1)
    m0_all = outcome_model.predict(contexts, treatment=0)
    e_all = propensity_model.predict_proba(contexts)[:, 1]
    e_all = np.clip(e_all, clip_bound, 1.0 - clip_bound)

    # Vectorized DR formula
    treated_mask = treatments == 1
    dr_estimates[treated_mask] = (
        (m1_all - m0_all)[treated_mask] 
        + (outcomes - m1_all)[treated_mask] / e_all[treated_mask]
    )
    dr_estimates[~treated_mask] = (
        (m1_all - m0_all)[~treated_mask] 
        - (outcomes - m0_all)[~treated_mask] / (1.0 - e_all[~treated_mask])
    )

    return dr_estimates
```

### 4.4 FMA Aggregation (Executable Template)

```python
# fma/fma/aggregator.py
from typing import List
import numpy as np

def aggregate_fma(
    ciu_results: List[CIUResult],
    task_distribution: str,
    normalize: bool = True,
) -> List[FMAResult]:
    """
    Aggregate CIU scores into FMA under task distribution D.

    FMA(m_k; D) = E_{x_<k ~ D}[CIU(m_k | x_<k)]

    Args:
        ciu_results: list of CIU estimates
        task_distribution: identifier for task distribution (e.g., "gsm8k")
        normalize: whether to normalize scores to [0, 1]

    Returns:
        List of FMAResult grouped by operation_type
    """
    from collections import defaultdict

    # Group by operation type
    grouped = defaultdict(list)
    for result in ciu_results:
        grouped[result.span.operation_type].append(result.ciu_score)

    fma_results = []
    for op_type, scores in grouped.items():
        fma_score = float(np.mean(scores))
        fma_results.append(FMAResult(
            span_type=op_type,
            fma_score=fma_score,
            task_distribution=task_distribution,
            sample_count=len(scores),
        ))

    if normalize and len(fma_results) > 0:
        scores = np.array([r.fma_score for r in fma_results])
        min_score, max_score = scores.min(), scores.max()
        if max_score > min_score:
            for r in fma_results:
                r.fma_score = (r.fma_score - min_score) / (max_score - min_score)

    return fma_results

def compute_attribution_weights(
    fma_results: List[FMAResult],
    temperature: float = 1.0,
) -> Dict[str, float]:
    """
    Convert FMA scores to supervision weights.

    w_k = Normalize(FMA(m_k; D))
    """
    weights = {}
    for result in fma_results:
        weights[result.span_type] = result.fma_score / temperature

    # Softmax normalization
    import math
    exp_scores = {k: math.exp(v) for k, v in weights.items()}
    sum_exp = sum(exp_scores.values())
    return {k: v / sum_exp for k, v in exp_scores.items()}
```

---

## 5. Config Schema

All experiments MUST be config-driven.

Example:

```yaml
experiment:
  name: gsm8k_fma
  seed: 42

model:
  backbone: gpt-4
  temperature: 0.2
  max_tokens: 2048

data:
  dataset: gsm8k
  split: test

reflection:
  extractor: regex_v1
  operation_types:
    - self-reflection
    - self-evaluation
    - error_diagnosis
    - plan_revision
    - strategy_critique

intervention:
  type: masking
  preserve_length: true
  mask_token: "[REASONING_MASK]"

replacement:
  distribution: conditional
  similarity_threshold: 0.7
  length_tolerance: 0.2

perturbation:
  methods:
    - paraphrase
    - compression
    - contradiction_injection
  semantic_threshold: 0.85

matching:
  method: nearest_neighbor
  ratio: "1:1"
  replacement: false
  normalized_features: true
  features:
    - trajectory_length
    - token_budget
    - task_difficulty
    - reasoning_depth
    - reflection_density
    - step_index

dr:
  enabled: true
  propensity_model: logistic_regression
  outcome_model: ridge_regression
  propensity_clip: 0.01

fma:
  aggregation: task_distribution
  normalize: true
  temperature: 1.0

evaluation:
  metrics:
    - intervention_sensitivity
    - attribution_selectivity
    - utility_calibration
    - step_level_accuracy
    - calibration_error
    - task_success_rate
    - reasoning_robustness

logging:
  save_outputs: true
  save_config: true
  save_git_hash: true
```

---

## 6. Forbidden Patterns

The following patterns are STRICTLY forbidden.

### 6.1 No Naive Token Deletion

Never directly remove reflection spans in `intervene()`.

All interventions MUST preserve:

- token length
- positional structure
- autoregressive consistency

### 6.2 No Random Unconditional Replacement

Replacement spans MUST originate from:

`ConditionalDistribution.sample()`

Random unrelated replacement is forbidden.

**Current status**: ConditionalDistribution is NOT implemented. The pipeline uses random template swap, which is a known deviation. This deviation MUST be explicitly labeled as proxy evidence until conditional sampling is implemented.

### 6.3 No Overclaiming Raw Scores As Matched/DR Estimates

Final utility claims that invoke matched or doubly robust estimation MUST include:

- counterfactual matching
- doubly robust correction

Raw replay contrasts and proxy scores are allowed only when explicitly labeled as local, diagnostic, pilot, or proxy evidence. They must not be described as matched estimates, DR-corrected estimates, submission-ready real-task evidence, or PRM/filtering performance.

### 6.4 No Framing FMA as True Causal Effect

Forbidden terminology:

- true causal effect
- average treatment effect
- globally identifiable causal quantity

Correct terminology:

- functional attribution
- intervention-sensitive utility
- local functional influence

### 6.5 No Monolithic Scripts

All implementations MUST be modularized.

Forbidden:

- giant notebook pipelines
- single-file experiment runners
- hardcoded evaluation logic

### 6.6 No Global Aggregation Without Task Distribution

FMA MUST always condition on:

`task distribution D`

Global utility aggregation without task conditioning is forbidden.

---

## 7. Testing & Output Contracts

Every module MUST expose deterministic tests.

### 7.1 Intervention Tests

```python
def test_masking_preserves_token_count():
    """Verify masking intervention preserves total token count."""
    pass

def test_masking_preserves_position():
    """Verify span start/end indices unchanged after intervention."""
    pass

def test_replacement_semantic_similarity():
    """Verify replacement span satisfies cosine similarity > delta."""
    pass

def test_perturbation_preserves_topic():
    """Verify perturbed span maintains core reasoning topic."""
    pass
```

### 7.2 Matching Tests

```python
def test_matching_valid_pairs():
    """Verify matched pairs have valid treated and control samples."""
    pass

def test_matching_no_replacement():
    """Verify no control sample is used more than once."""
    pass

def test_matching_feature_normalization():
    """Verify features are normalized before distance computation."""
    pass
```

### 7.3 DR Estimator Tests

```python
def test_propensity_bounded():
    """Verify propensity scores are clipped away from 0 and 1."""
    pass

def test_dr_estimate_finite():
    """Verify DR estimate is finite and not NaN."""
    pass

def test_dr_more_stable_than_ipw():
    """Verify DR variance lower than inverse propensity weighting."""
    pass
```

### 7.4 Output Schema

All experiment outputs MUST follow JSON schema:

```json
{
  "sample_id": "string",
  "task": "string",
  "task_type": "string",
  "ciu": 0.0,
  "fma": 0.0,
  "matched": true,
  "propensity": 0.0,
  "intervention_type": "masking | replacement | perturbation",
  "operation_type": "self-reflection | self-evaluation | error_diagnosis | plan_revision | strategy_critique",
  "context_length": 0,
  "trajectory_length": 0
}
```

### 7.5 Evaluation Reports

Each experiment MUST produce:

- `metrics/attribution.json`: intervention sensitivity, selectivity, calibration
- `metrics/supervision.json`: step-level accuracy, calibration error
- `metrics/downstream.json`: task success rate, reasoning robustness
- `metrics/intervention_stats.json`: intervention type distribution, matching rates

---

## 8. Logging Requirements

Every run MUST save:

- experiment config (YAML snapshot)
- git commit hash
- random seed
- model version / API version
- intervention statistics
- matching statistics (match rate, mean distance)
- DR diagnostics (propensity distribution, outcome model R²)
- evaluation metrics

Logs MUST be reproducible.

All outputs should be stored under:

```text
outputs/
    experiment_name/
        configs/
            config.yaml
        logs/
            run.log
        metrics/
            attribution.json
            supervision.json
            downstream.json
            intervention_stats.json
        traces/
            intervention_traces.jsonl
```

---

## 9. Theoretical Constraints

The repository MUST explicitly acknowledge:

### 9.1 Non-Identifiability

The framework does NOT recover Rubin-style true causal effects.

### 9.2 Distribution Dependence

FMA depends on reasoning distribution D. Results are not universal.

### 9.3 Observable Context Assumption

The framework conditions only on observable reasoning traces x_<k.

Latent cognitive states are NOT assumed observable.

### 9.4 Approximate Intervention

Structure-preserving masking only approximates idealized cognitive interventions.

The framework studies:

> functional organization of reflective cognition.

PRM improvement is treated only as a downstream application.

---

## 10. Data Validation Status

### 10.1 Synthetic Data

- 800 traces / 2400 reflective steps (synthetic)
- Phase 5-7 and Stage 2 confirmatory results are limited to synthetic data
- External validity is unconfirmed

### 10.2 Real-Task Validation

All 6 real-task validation routes have failed:

| Route | Status | Outcome |
|---|---|---|
| v2 (s_FMA stochastic smoke) | **FAILED** | Sparse signal (0 nonzero GSM8K delta) |
| v2.1 (evidence target) | **ABANDONED** | Full validation failed quality gate; downstream filtering signal negative |
| v2.2 (exploratory) | **FAILED** | Sparse signal (0 nonzero GSM8K delta) |
| v3 (real-task DELETE) | **FAILED** | Data scarcity: strict deduplication exhausted all rows (GSM8K 0, HotpotQA 0) |
| v3.1 (real-task REPLACE) | **FAILED** | Sparse signal on both tasks |
| Legacy pilot | **BLOCKED** | Preflight drift failure |

No real-task validation evidence may be claimed. All claims involving real-task data MUST be labeled `failed_validation` or `pilot_blocked`.

### 10.3 Deduplication Root Cause

The v3 route uses 6-key OR-logic deduplication against prior artifacts. This, combined with:
- GSM8K rows having empty aliases (causing sentinel hash collisions)
- HotpotQA validation split fully consumed by prior v2/v2.1/v2.2 routes

results in 0 eligible rows after deduplication. An AND-logic core dedup (3-key: sample_id, question_hash, answer_hash) is implemented in the manifest generator but still produces 0 rows because the same data splits were used across all prior routes.
