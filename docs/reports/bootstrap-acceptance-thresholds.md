# Bootstrap Acceptance Thresholds: Analysis and Proposal

**Date:** 2025-02-22  
**Author:** Nash (AI assistant), based on findings by Stefan  
**Status:** Proposal  

---

## 1. Observation: 25 Days of Zero Adaptation

Stefan ran the **Lehman Month** scenario — a 6-bank, 25-day crisis simulation with escalating stress events — using the "Between each day" (`every_scenario_day`) optimization schedule. The AI (GLM-4.7) was configured to propose policy updates after each simulated day.

**What happened:**
- The incumbent policy used `initial_liquidity_fraction = 1.000` (commit 100% of available liquidity)
- Every day, the AI proposed `initial_liquidity_fraction ≈ 0.500`
- The bootstrap paired evaluation **rejected all 25 proposals**
- Result: the simulation ran 25 days of pure crisis dynamics with no policy adaptation whatsoever

**Why the rejections were technically correct:**

The incumbent `frac=1.000` policy achieves **100% settlement rate** with zero delay penalties and zero deadline penalties. Its only cost is opportunity cost (holding excess liquidity). The proposed `frac=0.500` introduces settlement variance — under some seeds, transactions fail or are delayed, incurring penalties. In a crisis scenario with elevated transaction volumes and counterparty stress, reducing liquidity allocation is inherently riskier.

The bootstrap test correctly identifies that `frac=0.500` cannot be proven superior to `frac=1.000` at the required significance level. The confidence interval on the paired delta crosses zero (or is positive), meaning the improvement is not statistically significant.

**The deeper problem:** GLM-4.7 was not generating rich decision trees with conditional logic — just flat fraction adjustments. A sophisticated policy might reduce fraction *selectively* (e.g., hold back liquidity only for low-priority payments), but a blanket reduction from 1.0 to 0.5 is a blunt instrument that the bootstrap rightly penalizes.

---

## 2. Why the Bootstrap Is Too Conservative for Crisis Scenarios

### 2.1 Current Bootstrap Logic

The acceptance gate lives in `web/backend/app/bootstrap_eval.py` → `WebBootstrapEvaluator`. The acceptance criteria are:

```python
# Three conditions must ALL pass:
1. delta_sum < 0          # New policy must be cheaper overall
2. cv < cv_threshold      # CV of deltas must be below 0.5
3. ci_upper < 0           # 95% CI upper bound must be below zero
```

Where:
- `delta = new_cost - old_cost` (negative = improvement)
- `cv_threshold = 0.5` (hardcoded default)
- CI uses `z = 1.96` (95% confidence, hardcoded)
- `num_samples` defaults to the game's `num_eval_samples` setting

### 2.2 Why This Fails in Crisis Scenarios

**High variance under stress:** Crisis scenarios produce high cost variance across seeds. When the incumbent has near-zero variance (frac=1.0 → always settles everything), any alternative with non-zero variance will struggle to pass the CI test, even if its mean cost is lower.

**Asymmetric cost structure:** The opportunity cost of holding 100% liquidity is constant and low. The penalty for failing to settle is catastrophic and variable. This creates an asymmetry where conservative policies always "look" better to a symmetric statistical test.

**No exploration incentive:** The bootstrap acts as a pure exploitation gate. In a 25-day scenario, there is zero exploration budget. If the first proposal is rejected, the AI sees the same context (incumbent unchanged) and proposes something similar, which is again rejected. This creates a degenerate loop.

**Sample size limitation:** With `num_eval_samples` set to a moderate number (e.g., 5-10), the CI is wide. Combined with the requirement that `ci_upper < 0`, this means only large, consistent improvements can pass — exactly the kind that are unlikely when moving away from a safe-but-expensive policy during a crisis.

### 2.3 The Conservatism Paradox

The bootstrap was designed to prevent reckless policy changes. But in the Lehman Month scenario, it prevents *all* policy changes, which means:
- No learning occurs
- The experiment produces no useful optimization data
- The scenario is reduced to a pure simulation replay with static policies
- The research question ("can AI adapt policies during a crisis?") goes unanswered

---

## 3. Proposed Solution: Configurable Per-Bank Acceptance Thresholds

### 3.1 Design Concept

Different banks have different risk appetites. A conservative central counterparty should require strong statistical evidence before changing policy. An aggressive trading bank might accept higher-variance proposals to explore the cost landscape. This maps directly to real-world banking:

| Profile | Real-World Analog | Behavior |
|---------|-------------------|----------|
| **Conservative** | Central bank, systemically important FMI | High confidence required (99%), low CV threshold, reject anything uncertain |
| **Moderate** | Large commercial bank | Standard confidence (95%), moderate CV threshold |
| **Aggressive** | Trading desk, fintech | Lower confidence (80-90%), high CV threshold, willing to explore |
| **Exploration** | Research/sandbox mode | Accept any improvement in mean, ignore CI |

### 3.2 Configurable Parameters

Three parameters should be exposed per bank:

#### `confidence_level` (float, 0.0–1.0, default: 0.95)
Controls the z-score used for the CI calculation:
- `0.99` → z=2.576 (very conservative)
- `0.95` → z=1.960 (current default)
- `0.90` → z=1.645
- `0.80` → z=1.282 (aggressive)

#### `cv_threshold` (float, 0.0–∞, default: 0.5)
Maximum allowed coefficient of variation on paired deltas:
- `0.3` → very stable results required (conservative)
- `0.5` → current default
- `1.0` → high variance tolerated (aggressive)
- `∞` (or disabled) → ignore CV entirely

#### `acceptance_mode` (enum, default: "statistical")
Controls which acceptance criteria are applied:
- `"statistical"` — current behavior: all three checks (delta_sum < 0, CV < threshold, CI upper < 0)
- `"mean_only"` — accept if `mean_delta < 0` (new policy cheaper on average), ignore CI and CV
- `"always_accept"` — accept any valid policy (pure exploration, useful for benchmarking)
- `"lenient"` — accept if `delta_sum < 0` and CI check uses the configured confidence level (skip CV check)

### 3.3 Per-Bank Risk Profiles (Presets)

To simplify configuration, offer named presets:

```python
RISK_PROFILES = {
    "conservative": {
        "confidence_level": 0.99,
        "cv_threshold": 0.3,
        "acceptance_mode": "statistical",
    },
    "moderate": {
        "confidence_level": 0.95,
        "cv_threshold": 0.5,
        "acceptance_mode": "statistical",
    },
    "aggressive": {
        "confidence_level": 0.80,
        "cv_threshold": 1.5,
        "acceptance_mode": "lenient",
    },
    "exploration": {
        "confidence_level": 0.5,
        "cv_threshold": 999.0,
        "acceptance_mode": "mean_only",
    },
}
```

### 3.4 Real-World Mapping

This design reflects genuine institutional differences:

- **Risk-averse institutions** (e.g., Riksbank, ECB) operate with mandate-driven conservatism. They would never adopt a policy that might cause settlement failures, even if it saves money on average. High confidence thresholds model this.
- **Commercially-driven banks** balance cost optimization against risk. They accept moderate uncertainty if the expected payoff is positive.
- **Aggressive participants** (hedge fund treasury, fintech) optimize for cost and are willing to accept occasional settlement friction if the expected savings are significant.

In a multi-bank simulation, having heterogeneous risk profiles creates **emergent dynamics**: aggressive banks explore while conservative banks anchor, producing a more realistic and interesting simulation.

---

## 4. Implementation Plan

### 4.1 Data Model Changes

**New dataclass for acceptance config:**

```python
# web/backend/app/bootstrap_eval.py

from enum import Enum

class AcceptanceMode(str, Enum):
    STATISTICAL = "statistical"
    MEAN_ONLY = "mean_only"
    ALWAYS_ACCEPT = "always_accept"
    LENIENT = "lenient"

@dataclass(frozen=True)
class AcceptanceConfig:
    confidence_level: float = 0.95
    cv_threshold: float = 0.5
    acceptance_mode: AcceptanceMode = AcceptanceMode.STATISTICAL
```

### 4.2 File Changes

#### `web/backend/app/bootstrap_eval.py`

**`WebBootstrapEvaluator`** changes:
1. Accept `AcceptanceConfig` in constructor (or per-call in `evaluate()`)
2. Replace hardcoded `1.96` with `scipy.stats.norm.ppf((1 + config.confidence_level) / 2)` (or a lookup table to avoid scipy dependency)
3. Apply `acceptance_mode` logic in the acceptance decision block
4. Pass `cv_threshold` from config instead of constructor

```python
class WebBootstrapEvaluator:
    def __init__(self, num_samples: int = 10, 
                 acceptance_config: AcceptanceConfig | None = None):
        self.num_samples = num_samples
        self.config = acceptance_config or AcceptanceConfig()
    
    def evaluate(self, ..., acceptance_config: AcceptanceConfig | None = None) -> EvaluationResult:
        config = acceptance_config or self.config
        # ... existing delta computation ...
        
        z = _z_score(config.confidence_level)  # 1.96 for 0.95, etc.
        ci_lower = int(mean_delta - z * se)
        ci_upper = int(mean_delta + z * se)
        
        accepted, rejection_reason = self._apply_acceptance(
            config, delta_sum, cv, ci_upper
        )
```

#### `web/backend/app/game.py`

**`Game.__init__`** changes:
1. Accept `acceptance_configs: dict[str, AcceptanceConfig]` mapping agent_id → config
2. Store as `self.acceptance_configs`
3. Pass per-agent config to `_run_bootstrap()`

**`Game._run_bootstrap`** changes:
```python
def _run_bootstrap(self, evaluator, aid: str, result: dict) -> dict:
    config = self.acceptance_configs.get(aid)  # None → default
    eval_result = evaluator.evaluate(
        ..., acceptance_config=config,
    )
```

**`Game.to_checkpoint` / `from_checkpoint`**:
- Serialize/deserialize `acceptance_configs`

#### `web/backend/app/routes.py` (or equivalent API route)

- Accept `acceptance_configs` in game creation payload
- Validate configs against allowed ranges
- Support both preset names ("aggressive") and custom configs

#### `web/frontend/src/`

- Add per-bank risk profile selector in game setup UI
- Options: dropdown per bank (Conservative / Moderate / Aggressive / Exploration / Custom)
- Custom mode exposes sliders for confidence_level, cv_threshold, acceptance_mode

### 4.3 API Surface

Game creation request body extension:

```json
{
  "acceptance_configs": {
    "BANK_A": {"preset": "conservative"},
    "BANK_B": {"preset": "aggressive"},
    "BANK_C": {
      "confidence_level": 0.90,
      "cv_threshold": 0.8,
      "acceptance_mode": "lenient"
    }
  }
}
```

### 4.4 Migration

Existing games without `acceptance_configs` default to `AcceptanceConfig()` (current behavior = moderate). No breaking changes.

---

## 5. Alternative and Complementary Approaches

### 5.1 Reduce `num_eval_samples`

Fewer samples → wider CI → but the CI check becomes meaningless. With 1 sample, the bootstrap is disabled entirely (current behavior when `num_eval_samples=1`). This is a blunt workaround, not a solution.

**Verdict:** Quick hack for experiments, but doesn't model institutional risk appetite.

### 5.2 Warm-Start with Known-Good Policies

Instead of starting at `frac=1.0`, start the AI with a policy that's already near-optimal for the scenario type. For crisis scenarios, this might be `frac=0.85` with conditional logic. The AI then makes smaller adjustments that are more likely to pass the bootstrap.

**Implementation:** Add `starting_policies` per scenario template (already supported in `Game.__init__`).

**Verdict:** Good complementary approach. Reduces the "cold start" problem.

### 5.3 Crisis-Specific Prompt Engineering

The current prompts don't differentiate between calm and crisis scenarios. Adding crisis-aware context could help the LLM propose more nuanced policies:

- "You are in a crisis scenario. Settlement failures are extremely costly. Prefer conservative adjustments."
- Include scenario event descriptions (bank failures, liquidity shocks) in the prompt context
- Guide toward decision-tree policies rather than flat fraction changes

**Implementation:** Extend `build_system_prompt()` in `api/payment_simulator/ai_cash_mgmt/prompts/system_prompt_builder.py` with scenario-type awareness.

**Verdict:** High impact. The root cause of Stefan's observation is partly that GLM-4.7 only tweaks fractions. Better prompting could unlock richer policies.

### 5.4 Adaptive Confidence Decay

Start with strict confidence (99%) and gradually relax it if policies keep being rejected. After N consecutive rejections, lower the confidence level by a step. This creates an automatic exploration pressure.

```python
effective_confidence = max(
    config.min_confidence,
    config.confidence_level - (consecutive_rejections * config.decay_rate)
)
```

**Verdict:** Elegant but adds complexity. Could combine with per-bank profiles (each bank has its own decay rate).

### 5.5 Separate Exploration Budget

Allow a configurable number of "free" policy updates that bypass the bootstrap entirely. E.g., the first 3 proposals are always accepted, then the bootstrap kicks in.

**Implementation:** Add `exploration_rounds: int` to game config. In `_run_bootstrap()`, skip evaluation if `current_day < exploration_rounds`.

**Verdict:** Simple, effective for research scenarios. Less realistic for production simulations.

### 5.6 Multi-Objective Acceptance

Instead of a single cost metric, evaluate on multiple dimensions (cost, settlement rate, delay) and accept if the policy is Pareto-improving or within a tolerance band.

**Verdict:** Architecturally significant change. Worth considering for v2 but out of scope here.

---

## 6. Recommended Next Steps

1. **Immediate (unblocks Stefan's research):** Implement `acceptance_mode: "mean_only"` and `confidence_level` as per-game (not yet per-bank) settings. This is a ~2-hour change in `bootstrap_eval.py` + `game.py`.

2. **Short-term:** Full per-bank `AcceptanceConfig` with presets. UI integration with risk profile selector. ~1-2 day effort.

3. **Medium-term:** Prompt engineering for crisis scenarios + warm-start policies. Adaptive confidence decay. ~1 week.

4. **Long-term:** Rich decision tree generation (requires model upgrade beyond GLM-4.7 or fine-tuning). Multi-objective acceptance.

---

## Appendix: Key Code Paths

| Component | File | Key Class/Function |
|-----------|------|--------------------|
| Bootstrap evaluator | `web/backend/app/bootstrap_eval.py` | `WebBootstrapEvaluator.evaluate()` |
| Acceptance decision | `web/backend/app/bootstrap_eval.py` | Lines 85-98 (acceptance criteria block) |
| Bootstrap invocation | `web/backend/app/game.py` | `Game._run_bootstrap()` |
| Game config | `web/backend/app/game.py` | `Game.__init__()` — `num_eval_samples`, `cv_threshold` |
| Evaluator creation | `web/backend/app/game.py` | `Game.optimize_policies_streaming()` — `WebBootstrapEvaluator(num_samples=..., cv_threshold=0.5)` |
| LLM optimization | `web/backend/app/streaming_optimizer.py` | `stream_optimize()` |
| Policy optimizer | `api/payment_simulator/ai_cash_mgmt/optimization/policy_optimizer.py` | `PolicyOptimizer.optimize()` |
| Prompt builder | `api/payment_simulator/ai_cash_mgmt/prompts/system_prompt_builder.py` | `build_system_prompt()` |
| CI calculation | `web/backend/app/bootstrap_eval.py` | Lines 72-78 (hardcoded `1.96`) |
