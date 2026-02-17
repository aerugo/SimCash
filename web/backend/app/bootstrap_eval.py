"""Bootstrap paired evaluation for web game policy comparison.

Convention: delta = new_cost - old_cost. Negative delta = improvement.
Accept if delta_sum < 0, CV < threshold, and 95% CI upper < 0.
"""
from __future__ import annotations

import concurrent.futures
import copy
import json
import math
import statistics
from dataclasses import dataclass, field
from typing import Any

from payment_simulator._core import Orchestrator
from payment_simulator.config.schemas import SimulationConfig


@dataclass(frozen=True)
class EvaluationResult:
    """Result of paired bootstrap evaluation."""
    delta_sum: int           # Sum of paired deltas. Negative = improvement.
    mean_delta: int          # Mean paired delta
    cv: float                # Coefficient of variation of deltas
    ci_lower: int            # 95% CI lower bound on mean_delta
    ci_upper: int            # 95% CI upper bound on mean_delta
    accepted: bool           # Whether the new policy was accepted
    rejection_reason: str    # Empty if accepted
    paired_deltas: list[dict]  # Per-seed delta details
    num_samples: int
    old_mean_cost: int       # Mean cost under old policy
    new_mean_cost: int       # Mean cost under new policy


class WebBootstrapEvaluator:
    """Evaluate policy proposals using paired comparison on same seeds.

    For each of N seeds:
      1. Run simulation with old policy → cost_old
      2. Run simulation with new policy → cost_new
      3. delta = cost_new - cost_old  (negative = new is cheaper)

    Accept if:
      - delta_sum < 0 (new policy is cheaper overall)
      - CV of deltas < cv_threshold (result is stable)
      - 95% CI upper bound < 0 (statistically significant improvement)
    """

    def __init__(self, num_samples: int = 10, cv_threshold: float = 0.5):
        self.num_samples = num_samples
        self.cv_threshold = cv_threshold

    def evaluate(
        self,
        raw_yaml: dict,
        agent_id: str,
        old_policy: dict,
        new_policy: dict,
        base_seed: int,
        other_policies: dict[str, dict] | None = None,
    ) -> EvaluationResult:
        seeds = [base_seed + i * 1000 for i in range(self.num_samples)]

        if self.num_samples > 1:
            # Parallel: use GIL-releasing run_and_get_total_cost() with threads
            with concurrent.futures.ThreadPoolExecutor(max_workers=min(self.num_samples, 8)) as pool:
                old_futures = [pool.submit(self._run_sim_fast, raw_yaml, agent_id, old_policy, s, other_policies) for s in seeds]
                new_futures = [pool.submit(self._run_sim_fast, raw_yaml, agent_id, new_policy, s, other_policies) for s in seeds]
                old_costs = [f.result() for f in old_futures]
                new_costs = [f.result() for f in new_futures]
        else:
            # Single sample: no thread overhead
            old_costs = [self._run_sim_fast(raw_yaml, agent_id, old_policy, seeds[0], other_policies)]
            new_costs = [self._run_sim_fast(raw_yaml, agent_id, new_policy, seeds[0], other_policies)]

        deltas = [new - old for new, old in zip(new_costs, old_costs)]

        delta_sum = sum(deltas)
        mean_delta = delta_sum // self.num_samples if self.num_samples > 0 else 0

        # CV of deltas
        if len(deltas) >= 2 and mean_delta != 0:
            std = statistics.stdev(deltas)
            cv = abs(std / mean_delta)
        else:
            cv = 0.0

        # 95% CI
        if len(deltas) >= 2:
            std = statistics.stdev(deltas)
            se = std / math.sqrt(len(deltas))
            ci_lower = int(mean_delta - 1.96 * se)
            ci_upper = int(mean_delta + 1.96 * se)
        else:
            ci_lower = mean_delta
            ci_upper = mean_delta

        # Acceptance criteria
        accepted = True
        rejection_reason = ""

        if delta_sum == 0:
            # Same policy or no change — accept (no harm)
            accepted = True
        elif delta_sum >= 0:
            accepted = False
            rejection_reason = f"No improvement: delta_sum={delta_sum} (new policy not cheaper)"
        elif cv > self.cv_threshold:
            accepted = False
            rejection_reason = f"CV too high: {cv:.3f} > {self.cv_threshold}"
        elif ci_upper >= 0:
            accepted = False
            rejection_reason = f"Not significant: 95% CI upper={ci_upper} crosses zero"

        paired_details = [
            {
                "sample_idx": i,
                "seed": base_seed + i * 1000,
                "old_cost": old_costs[i],
                "new_cost": new_costs[i],
                "delta": deltas[i],
            }
            for i in range(self.num_samples)
        ]

        return EvaluationResult(
            delta_sum=delta_sum,
            mean_delta=mean_delta,
            cv=round(cv, 4),
            ci_lower=ci_lower,
            ci_upper=ci_upper,
            accepted=accepted,
            rejection_reason=rejection_reason,
            paired_deltas=paired_details,
            num_samples=self.num_samples,
            old_mean_cost=sum(old_costs) // self.num_samples if self.num_samples else 0,
            new_mean_cost=sum(new_costs) // self.num_samples if self.num_samples else 0,
        )

    def _prepare_orchestrator(
        self,
        raw_yaml: dict,
        agent_id: str,
        policy: dict,
        seed: int,
        other_policies: dict[str, dict] | None = None,
    ) -> tuple:
        """Prepare an Orchestrator and return (orch, num_ticks). Does not run."""
        scenario = copy.deepcopy(raw_yaml)

        for agent_cfg in scenario.get("agents", []):
            aid = agent_cfg.get("id")
            if aid == agent_id:
                p = policy
            elif other_policies and aid in other_policies:
                p = other_policies[aid]
            else:
                continue
            fraction = p.get("parameters", {}).get("initial_liquidity_fraction", 1.0)
            agent_cfg["liquidity_allocation_fraction"] = fraction
            agent_cfg["policy"] = {"type": "InlineJson", "json_string": json.dumps(p)}

        scenario.setdefault("simulation", {})["rng_seed"] = seed

        sim_config = SimulationConfig.from_dict(scenario)
        ffi_config = sim_config.to_ffi_dict()
        orch = Orchestrator.new(ffi_config)
        ticks = ffi_config["ticks_per_day"] * ffi_config["num_days"]
        return orch, ticks

    def _run_sim_fast(
        self,
        raw_yaml: dict,
        agent_id: str,
        policy: dict,
        seed: int,
        other_policies: dict[str, dict] | None = None,
    ) -> int:
        """Run simulation using GIL-releasing FFI method (thread-safe)."""
        orch, ticks = self._prepare_orchestrator(raw_yaml, agent_id, policy, seed, other_policies)
        return orch.run_and_get_total_cost(agent_id, ticks)

    def _run_sim(
        self,
        raw_yaml: dict,
        agent_id: str,
        policy: dict,
        seed: int,
        other_policies: dict[str, dict] | None = None,
    ) -> int:
        """Run simulation using sequential tick loop (legacy, kept for compatibility)."""
        orch, ticks = self._prepare_orchestrator(raw_yaml, agent_id, policy, seed, other_policies)
        for _ in range(ticks):
            orch.tick()
        ac = orch.get_agent_accumulated_costs(agent_id)
        return int(ac.get("total_cost", 0))
